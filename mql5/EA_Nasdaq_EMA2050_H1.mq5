//+------------------------------------------------------------------+
//| EA_Nasdaq_EMA2050_H1.mq5                                         |
//| Cruce de EMAs 20/50 en H1 (proyecto nasdaq_structure_memory_bot) |
//|                                                                  |
//| Mismas reglas que el backtest (scripts/run_ema_cross.py,         |
//| variante H1|20/50|2R|ambas) y que el módulo Python               |
//| src/nsmb/strategies/ema_cross.py:                                |
//|  - Al CIERRE de una vela H1 en que la EMA 20 cruza la EMA 50:    |
//|    compra (cruza hacia arriba) o venta (hacia abajo), a mercado. |
//|  - Stop a 1,5 x ATR14(H1) desde el precio de entrada.            |
//|    Objetivo 2 R. Ambos se ponen en el broker al abrir.           |
//|  - Si llega el cruce contrario con la posición abierta: cierra y |
//|    abre la contraria.                                            |
//|  - No abre si el spread supera InpMaxSpreadPrice.                |
//| Riesgo: InpRiskPct del equity por operación (0,25 % por defecto).|
//| Si el lote mínimo arriesga más que eso, NO opera.                |
//| Sin martingala, sin cobertura, una sola posición a la vez.       |
//| Límite de pérdida diaria: InpMaxDailyLossPct (1 %).              |
//| Por defecto SOLO opera en cuentas DEMO (InpOnlyDemo).            |
//|                                                                  |
//| AVISO: en el backtest esta regla NO pasó la prueba estadística   |
//| (+0,15 R en 2021-23, +0,03 R en 2024, +0,04 R en 2025-26).       |
//| Probarla primero en el Probador de estrategias y en demo.        |
//+------------------------------------------------------------------+
#property copyright "nasdaq_structure_memory_bot"
#property version   "1.00"

#include <Trade\Trade.mqh>

input int    InpFastEMA          = 20;      // EMA rápida
input int    InpSlowEMA          = 50;      // EMA lenta
input int    InpATRPeriod        = 14;      // Periodo ATR (H1)
input double InpStopATR          = 1.5;     // Stop = x ATR
input double InpTargetR          = 2.0;     // Objetivo en R
input double InpRiskPct          = 0.25;    // Riesgo por operación (% del equity)
input double InpMaxDailyLossPct  = 1.0;     // Pérdida diaria máxima (% del equity al empezar el día)
input double InpMaxSpreadPrice   = 8.0;     // Spread máximo en PRECIO (USTECm: 8,0 = 800 puntos)
input bool   InpOnlyDemo         = true;    // Solo cuentas demo (poner false bajo tu responsabilidad)
input long   InpMagic            = 20261021;// Número mágico
input int    InpSlippagePoints   = 30;      // Desviación máxima en puntos

CTrade   trade;
int      hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hATR = INVALID_HANDLE;
datetime lastBar = 0;
datetime dayStart = 0;
double   dayStartEquity = 0.0;

//+------------------------------------------------------------------+
int OnInit()
{
   if(InpFastEMA <= 0 || InpSlowEMA <= InpFastEMA || InpStopATR <= 0 || InpTargetR <= 0 ||
      InpRiskPct <= 0 || InpRiskPct > 2.0)
   {
      Print("Parámetros no válidos (riesgo máximo permitido 2 %).");
      return INIT_PARAMETERS_INCORRECT;
   }
   if(InpOnlyDemo && !MQLInfoInteger(MQL_TESTER) && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("La cuenta no es DEMO y InpOnlyDemo=true: el EA no se ejecuta.");
      return INIT_FAILED;
   }
   hFast = iMA(_Symbol, PERIOD_H1, InpFastEMA, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, PERIOD_H1, InpSlowEMA, 0, MODE_EMA, PRICE_CLOSE);
   hATR  = iATR(_Symbol, PERIOD_H1, InpATRPeriod);
   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hATR == INVALID_HANDLE)
   {
      Print("No se pudieron crear los indicadores.");
      return INIT_FAILED;
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   lastBar = iTime(_Symbol, PERIOD_H1, 0);     // no actuar sobre un cruce viejo al arrancar
   ResetDay();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(hFast != INVALID_HANDLE) IndicatorRelease(hFast);
   if(hSlow != INVALID_HANDLE) IndicatorRelease(hSlow);
   if(hATR  != INVALID_HANDLE) IndicatorRelease(hATR);
}

//+------------------------------------------------------------------+
void ResetDay()
{
   MqlDateTime t;
   TimeToStruct(TimeCurrent(), t);
   t.hour = 0; t.min = 0; t.sec = 0;
   dayStart = StructToTime(t);
   dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY);
}

bool DailyLossHit()
{
   if(TimeCurrent() >= dayStart + 86400) ResetDay();
   if(dayStartEquity <= 0) return true;
   double lossPct = (dayStartEquity - AccountInfoDouble(ACCOUNT_EQUITY)) / dayStartEquity * 100.0;
   return lossPct >= InpMaxDailyLossPct;
}

// Ticket de la posición de este EA en este símbolo (0 si no hay)
ulong MyPosition(int &dir)
{
   dir = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      dir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      return tk;
   }
   return 0;
}

// Lote para arriesgar InpRiskPct con un stop a stopDist (en precio). 0 si el mínimo arriesga más.
double LotForRisk(double stopDist)
{
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0) tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double vMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(tickSize <= 0 || tickValue <= 0 || vStep <= 0 || stopDist <= 0) return 0.0;
   double riskMoney   = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
   double lossPerLot  = stopDist / tickSize * tickValue;
   double lot = MathFloor(riskMoney / lossPerLot / vStep + 1e-9) * vStep;
   if(lot < vMin) return 0.0;                   // no se sube al mínimo: arriesgaría de más
   lot = MathMin(lot, vMax);
   int digits = (int)MathMax(0, MathRound(-MathLog10(vStep)));
   return NormalizeDouble(lot, digits);
}

//+------------------------------------------------------------------+
void OnTick()
{
   datetime bar = iTime(_Symbol, PERIOD_H1, 0);
   if(bar == 0 || bar == lastBar) return;       // solo una vez, al abrir cada vela H1 nueva
   lastBar = bar;

   double f[2], s[2], a[1];
   // índice 1 = última vela H1 cerrada, índice 2 = la anterior
   if(CopyBuffer(hFast, 0, 1, 2, f) != 2 || CopyBuffer(hSlow, 0, 1, 2, s) != 2 || CopyBuffer(hATR, 0, 1, 1, a) != 1)
   {
      Print("Sin datos de indicadores; se espera a la próxima vela.");
      lastBar = 0;                              // reintentar en el siguiente tick
      return;
   }
   // CopyBuffer devuelve de más antiguo a más reciente: f[0] = vela 2, f[1] = vela 1
   int sideNow  = (f[1] > s[1]) ? 1 : ((f[1] < s[1]) ? -1 : 0);
   int sidePrev = (f[0] > s[0]) ? 1 : ((f[0] < s[0]) ? -1 : 0);
   int signal = 0;
   if(sideNow > 0 && sidePrev <= 0) signal = 1;
   if(sideNow < 0 && sidePrev >= 0) signal = -1;
   if(signal == 0) return;

   // 1) cruce contrario: cerrar la posición abierta
   int dir;
   ulong tk = MyPosition(dir);
   if(tk != 0 && dir == -signal)
   {
      if(!trade.PositionClose(tk))
      {
         PrintFormat("No se pudo cerrar la posición %I64u: %d %s", tk, trade.ResultRetcode(), trade.ResultRetcodeDescription());
         return;                                // no abrir otra con una abierta
      }
      tk = MyPosition(dir);
   }
   if(tk != 0) return;                           // una sola posición a la vez

   // 2) filtros antes de abrir
   if(DailyLossHit()) { Print("Límite de pérdida diaria alcanzado: no se abre."); return; }
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) { Print("Sin precio."); return; }
   double spread = tick.ask - tick.bid;
   if(spread > InpMaxSpreadPrice) { PrintFormat("Spread alto (%.2f): no se abre.", spread); return; }

   double stopDist = InpStopATR * a[0];
   double lot = LotForRisk(stopDist);
   if(lot <= 0) { PrintFormat("El lote mínimo arriesga más del %.2f %% (stop %.2f): no se abre.", InpRiskPct, stopDist); return; }

   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double minDist = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(stopDist <= minDist) { Print("Stop demasiado cerca para el broker: no se abre."); return; }

   bool ok;
   if(signal > 0)
   {
      double px = tick.ask;
      double sl = NormalizeDouble(px - stopDist, digits);
      double tp = NormalizeDouble(px + InpTargetR * stopDist, digits);
      ok = trade.Buy(lot, _Symbol, 0.0, sl, tp, "EMA2050H1");
   }
   else
   {
      double px = tick.bid;
      double sl = NormalizeDouble(px + stopDist, digits);
      double tp = NormalizeDouble(px - InpTargetR * stopDist, digits);
      ok = trade.Sell(lot, _Symbol, 0.0, sl, tp, "EMA2050H1");
   }
   uint rc = trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_PLACED))
      PrintFormat("Orden rechazada: %d %s", rc, trade.ResultRetcodeDescription());
   else
      PrintFormat("Abierta %s %.2f lotes, stop %.2f puntos de precio, objetivo %.1f R",
                  signal > 0 ? "compra" : "venta", lot, stopDist, InpTargetR);
}
//+------------------------------------------------------------------+
