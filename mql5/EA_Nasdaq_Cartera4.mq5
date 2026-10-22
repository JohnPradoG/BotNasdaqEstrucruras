//+------------------------------------------------------------------+
//| EA_Nasdaq_Cartera4.mq5                                           |
//| Un solo EA con las 4 estrategias del proyecto en USTECm:         |
//|   1) ORB15  2) ORB5  3) NOISE (apertura de NY)  4) EMA 20/50 H1  |
//| Cada estrategia tiene su número mágico y como máximo UNA         |
//| operación abierta a la vez; pueden estar abiertas a la vez.      |
//|                                                                  |
//| Reglas = las del bot Python (src/nsmb/strategies/opening.py y    |
//| ema_cross.py), comprobadas contra el backtest:                   |
//|  ORB15: rango 9:30-9:45 NY; primera vela M5 que cierra fuera     |
//|    antes de 11:30; solo a favor de la media 50 de días (cierre   |
//|    diario 17:00 NY); stop al otro lado del rango; sin objetivo.  |
//|  ORB5: dirección de la 1.ª vela de 5 min (9:30-9:35) si no es    |
//|    casi plana (cuerpo >= 5 % del rango); stop en su extremo      |
//|    opuesto; objetivo 10 R.                                       |
//|  NOISE: banda = máx/mín(apertura 9:30, cierre previo) +- media   |
//|    de |movimiento desde la apertura| de las 14 sesiones previas  |
//|    a esa hora; revisión cada 30 min (10:00-15:30); fuera de la   |
//|    banda => entrar; volver a cruzarla => salir; stop de          |
//|    protección a 2 medias bandas.                                 |
//|  Las tres de apertura se cierran a las 15:57 NY y no operan en   |
//|  festivos de la bolsa de NY.                                     |
//|  EMA 20/50 H1: cruce al cierre de la vela H1; stop 1,5 ATR14;    |
//|    objetivo 2 R; en el cruce contrario cierra y gira.            |
//|                                                                  |
//| Riesgo: InpRiskPct por operación (0,25 %). Si el lote mínimo     |
//| arriesga más, NO opera esa señal. Pérdida diaria máx. de la      |
//| cuenta: InpMaxDailyLossPct. Sin martingala ni promediar.         |
//| Solo cuentas DEMO por defecto (InpOnlyDemo).                     |
//| Hora del servidor: Exness = UTC (InpServerUTCOffset = 0).        |
//| Telegram opcional: pegar token y chat ID en los parámetros.      |
//|                                                                  |
//| AVISO: ninguna de las 4 pasó la prueba estadística del proyecto. |
//| Probar en el Probador y en demo antes de pensar en dinero real.  |
//+------------------------------------------------------------------+
#property copyright "nasdaq_structure_memory_bot"
#property version   "1.10"

#include <Trade\Trade.mqh>

input bool   InpUseORB15         = true;     // Activar ORB15
input bool   InpUseORB5          = true;     // Activar ORB5
input bool   InpUseNoise         = true;     // Activar NOISE
input bool   InpUseEMA           = true;     // Activar EMA 20/50 H1
input double InpRiskPct          = 0.25;     // Riesgo por operación (% del equity)
input double InpMaxDailyLossPct  = 1.0;      // Pérdida diaria máxima de la cuenta (%)
input double InpMaxSpreadOpen    = 15.0;     // Spread máx. en PRECIO para las de apertura
input double InpMaxSpreadEMA     = 8.0;      // Spread máx. en PRECIO para la EMA
input int    InpMaxSignalAgeSec  = 180;      // Señal más vieja que esto: no se opera
input int    InpServerUTCOffset  = 0;        // Horas del servidor respecto a UTC (Exness: 0)
input bool   InpOnlyDemo         = true;     // Solo cuentas demo
input long   InpMagicBase        = 20261100; // Mágico base (+1 orb15, +2 orb5, +3 noise, +4 ema)
input int    InpSlippagePoints   = 30;       // Desviación máxima en puntos
input string InpTelegramToken    = "";       // Token del bot de Telegram (pegarlo aquí, nunca en el código)
input string InpTelegramChatID   = "";       // Chat ID de Telegram

// constantes de las reglas (congeladas)
#define OPEN_MIN    570      // 9:30
#define ORB15_END   585      // 9:45
#define ORB_LIMIT   690      // 11:30
#define FLAT_MIN    957      // 15:57
#define ORB5_TARGET 10.0
#define ORB5_FLAT   0.05
#define NOISE_LB    14
#define NOISE_STOP  2.0
#define EMA_FAST    20
#define EMA_SLOW    50
#define EMA_STOPATR 1.5
#define EMA_TARGET  2.0

enum { S_ORB15 = 1, S_ORB5 = 2, S_NOISE = 3, S_EMA = 4 };

CTrade trade;
int    hFast = INVALID_HANDLE, hSlow = INVALID_HANDLE, hATR = INVALID_HANDLE;
datetime lastH1 = 0;

// estado del día (NY)
int    curDay = 0;
bool   orb15Done, orb5Done, noiseReady, noiseChecked[12];
double sigma[12], noiseUpRef, noiseLoRef, biasDay;
bool   biasReady;
double dayStartEquity = 0; int equityDay = 0;

string HOLIDAYS = "20260101,20260119,20260216,20260403,20260525,20260619,20260703,20260907,20261126,20261225,"
                  + "20270101,20270118,20270215,20270326,20270531,20270618,20270705,20270906,20271125,20271224";

//+------------------------------------------------------------------+
//| Hora de Nueva York                                               |
//+------------------------------------------------------------------+
datetime NthSunday(int year, int month, int n)
{
   MqlDateTime t; t.year = year; t.mon = month; t.day = 1; t.hour = 0; t.min = 0; t.sec = 0;
   datetime d = StructToTime(t);
   TimeToStruct(d, t);
   int first = (7 - t.day_of_week) % 7;            // días hasta el primer domingo
   return d + (first + 7 * (n - 1)) * 86400;
}

// UTC -> hora local de NY (EE. UU.: horario de verano 2.º domingo de marzo - 1.er domingo de noviembre, a las 2:00)
datetime UtcToNY(datetime utc)
{
   MqlDateTime t; TimeToStruct(utc, t);
   datetime dstStart = NthSunday(t.year, 3, 2) + 7 * 3600;     // 2:00 EST = 7:00 UTC
   datetime dstEnd   = NthSunday(t.year, 11, 1) + 6 * 3600;    // 2:00 EDT = 6:00 UTC
   int off = (utc >= dstStart && utc < dstEnd) ? -4 : -5;
   return utc + off * 3600;
}

datetime ServerToUTC(datetime s) { return s - InpServerUTCOffset * 3600; }
datetime NYOf(datetime server)   { return UtcToNY(ServerToUTC(server)); }
int  NYDay(datetime ny)  { MqlDateTime t; TimeToStruct(ny, t); return t.year * 10000 + t.mon * 100 + t.day; }
int  NYMin(datetime ny)  { MqlDateTime t; TimeToStruct(ny, t); return t.hour * 60 + t.min; }
bool IsHoliday(int day)  { return StringFind(HOLIDAYS, IntegerToString(day)) >= 0; }

//+------------------------------------------------------------------+
//| Posiciones, lotes y órdenes                                      |
//+------------------------------------------------------------------+
long Magic(int s) { return InpMagicBase + s; }
string SName(int s) { return s == S_ORB15 ? "orb15" : s == S_ORB5 ? "orb5" : s == S_NOISE ? "noise" : "ema2050h1"; }

ulong FindPos(int s, int &dir)
{
   dir = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != Magic(s)) continue;
      dir = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? 1 : -1;
      return tk;
   }
   return 0;
}

bool ClosePos(int s, string why)
{
   int dir; ulong tk = FindPos(s, dir);
   if(tk == 0) return true;
   trade.SetExpertMagicNumber(Magic(s));
   bool ok = trade.PositionClose(tk);
   PrintFormat("[%s] cierre (%s): %s %d", SName(s), why, ok ? "ok" : "fallo", trade.ResultRetcode());
   return ok;
}

double LotForRisk(double stopDist)
{
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickValue <= 0) tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double vMin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN), vMax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(tickSize <= 0 || tickValue <= 0 || vStep <= 0 || stopDist <= 0) return 0.0;
   double lot = MathFloor(AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0 / (stopDist / tickSize * tickValue) / vStep + 1e-9) * vStep;
   if(lot < vMin) return 0.0;                       // no se sube al mínimo: arriesgaría de más
   lot = MathMin(lot, vMax);
   return NormalizeDouble(lot, (int)MathMax(0, MathRound(-MathLog10(vStep))));
}

bool DailyLossHit()
{
   int d = NYDay(NYOf(TimeCurrent()));
   if(d != equityDay) { equityDay = d; dayStartEquity = AccountInfoDouble(ACCOUNT_EQUITY); }
   if(dayStartEquity <= 0) return true;
   return (dayStartEquity - AccountInfoDouble(ACCOUNT_EQUITY)) / dayStartEquity * 100.0 >= InpMaxDailyLossPct;
}

// Abre a mercado. stopLevel: nivel sobre el BID (en ventas se le suma el spread), o stopDist > 0: distancia desde la
// entrada. targetR <= 0: sin objetivo.
bool OpenTrade(int s, int dir, double stopLevel, double stopDist, double targetR, double maxSpread, string why)
{
   int d0; if(FindPos(s, d0) != 0) return false;   // una operación por estrategia
   if(DailyLossHit())
   {
      PrintFormat("[%s] límite de pérdida diaria: no se abre", SName(s));
      Tg(StringFormat("%s: señal ignorada, límite de pérdida diaria del %.1f %% alcanzado", SName(s), InpMaxDailyLossPct));
      return false;
   }
   MqlTick tk; if(!SymbolInfoTick(_Symbol, tk)) return false;
   double spread = tk.ask - tk.bid;
   if(spread > maxSpread) { PrintFormat("[%s] spread alto %.2f: no se abre", SName(s), spread); return false; }
   double ref = dir > 0 ? tk.ask : tk.bid;
   double sl;
   if(stopDist > 0) sl = ref - dir * stopDist;
   else sl = dir > 0 ? stopLevel : stopLevel + spread;
   double risk = (ref - sl) * dir;
   double minDist = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(risk <= minDist) { PrintFormat("[%s] stop ya superado o demasiado cerca: no se abre", SName(s)); return false; }
   double lot = LotForRisk(risk);
   if(lot <= 0) { PrintFormat("[%s] el lote mínimo arriesga más del %.2f %% (stop %.2f): no se abre", SName(s), InpRiskPct, risk); return false; }
   int dg = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double tp = targetR > 0 ? NormalizeDouble(ref + dir * targetR * risk, dg) : 0.0;
   sl = NormalizeDouble(sl, dg);
   trade.SetExpertMagicNumber(Magic(s));
   bool ok = dir > 0 ? trade.Buy(lot, _Symbol, 0.0, sl, tp, "NSMB " + SName(s))
                     : trade.Sell(lot, _Symbol, 0.0, sl, tp, "NSMB " + SName(s));
   uint rc = trade.ResultRetcode();
   ok = ok && (rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_PLACED);
   PrintFormat("[%s] %s %s %.2f lotes, riesgo %.2f, %s: %s (%d)", SName(s), why, dir > 0 ? "compra" : "venta", lot, risk,
               targetR > 0 ? StringFormat("objetivo %.0f R", targetR) : "sin objetivo", ok ? "ok" : "rechazada", rc);
   if(ok) Tg(StringFormat("%s: ABRE %s %.2f lotes a %.2f | stop %.2f | %s | %s", SName(s), dir > 0 ? "COMPRA" : "VENTA",
                          lot, trade.ResultPrice(), sl, tp > 0 ? StringFormat("objetivo %.2f", tp) : "sin objetivo", why));
   else Tg(StringFormat("%s: orden RECHAZADA (%d %s)", SName(s), rc, trade.ResultRetcodeDescription()));
   return ok;
}

//+------------------------------------------------------------------+
//| Telegram (opcional): avisos de aperturas, cierres y bloqueos.    |
//| Requiere añadir https://api.telegram.org en Herramientas >       |
//| Opciones > Asesores Expertos > Permitir WebRequest.              |
//| El token va en los parámetros del EA, no en el código.           |
//+------------------------------------------------------------------+
string UrlEncode(string text)
{
   uchar src[]; StringToCharArray(text, src, 0, WHOLE_ARRAY, CP_UTF8);
   string out = "";
   for(int i = 0; i < ArraySize(src) - 1; i++)
   {
      uchar ch = src[i];
      if((ch >= '0' && ch <= '9') || (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') || ch == '-' || ch == '_' || ch == '.' || ch == '~')
         out += CharToString(ch);
      else
         out += StringFormat("%%%02X", ch);
   }
   return out;
}

void Tg(string text)
{
   if(InpTelegramToken == "" || InpTelegramChatID == "" || MQLInfoInteger(MQL_TESTER)) return;
   string url = "https://api.telegram.org/bot" + InpTelegramToken + "/sendMessage";
   string body = "chat_id=" + InpTelegramChatID + "&text=" + UrlEncode("[NSMB " + _Symbol + "] " + text);
   char post[], result[]; string rh;
   StringToCharArray(body, post, 0, StringLen(body), CP_UTF8);
   ResetLastError();
   int res = WebRequest("POST", url, "Content-Type: application/x-www-form-urlencoded\r\n", 5000, post, result, rh);
   if(res != 200)
      PrintFormat("Telegram no enviado (código %d, error %d). ¿Está https://api.telegram.org en Permitir WebRequest?", res, GetLastError());
}

//+------------------------------------------------------------------+
//| Datos                                                            |
//+------------------------------------------------------------------+
// Velas M1 CERRADAS de la sesión de hoy (NY 9:30-15:56); índice = minuto NY. Devuelve cuántas hay.
int TodayBars(datetime nyNow, MqlRates &out[], int &mins[])
{
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_M1, 0, 600, r);
   ArrayResize(out, 0); ArrayResize(mins, 0);
   if(n <= 0) return 0;
   int today = NYDay(nyNow);
   datetime nowSrv = TimeCurrent();
   for(int i = 0; i < n; i++)
   {
      if(r[i].time + 60 > nowSrv) continue;           // vela todavía abierta
      datetime ny = NYOf(r[i].time);
      int m = NYMin(ny);
      if(NYDay(ny) != today || m < OPEN_MIN || m >= FLAT_MIN) continue;
      int k = ArraySize(out);
      ArrayResize(out, k + 1); ArrayResize(mins, k + 1);
      out[k] = r[i]; mins[k] = m;
   }
   return ArraySize(out);
}

int FindMin(const int &mins[], int m) { for(int i = 0; i < ArraySize(mins); i++) if(mins[i] == m) return i; return -1; }

// Signo de (cierre diario - media 50) con el último día de trading CERRADO (día = cierre 17:00 NY).
// Se usan velas H1 (más ligeras que M1); un día cuenta si tiene al menos 2 velas H1 (~ las 120 M1 del backtest).
double SMA50Bias()
{
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_H1, 0, 2500, r);
   if(n < 200) return 0.0;
   double closes[]; int cnt[]; int keys[];
   int nd = 0, lastKey = -1;
   datetime nowSrv = TimeCurrent();
   for(int i = 0; i < n; i++)
   {
      if(r[i].time + 3600 > nowSrv) continue;
      int key = NYDay(NYOf(r[i].time) + 7 * 3600);   // día de trading: cierra a las 17:00 NY
      if(key != lastKey)
      {
         ArrayResize(closes, nd + 1); ArrayResize(cnt, nd + 1); ArrayResize(keys, nd + 1);
         keys[nd] = key; cnt[nd] = 0; nd++; lastKey = key;
      }
      closes[nd - 1] = r[i].close; cnt[nd - 1]++;
   }
   int curKey = NYDay(NYOf(nowSrv) + 7 * 3600);
   double c[]; int m = 0;
   for(int i = 0; i < nd; i++)
      if(keys[i] < curKey && cnt[i] >= 2) { ArrayResize(c, m + 1); c[m++] = closes[i]; }
   if(m < 50) return 0.0;
   double s = 0; for(int i = m - 50; i < m; i++) s += c[i];
   double diff = c[m - 1] - s / 50.0;
   return diff > 0 ? 1.0 : (diff < 0 ? -1.0 : 0.0);
}

// Banda del NOISE para hoy: sigma en cada revisión y referencias. false si no hay 14 sesiones previas completas.
bool PrepareNoise(datetime nyNow, double todayOpen)
{
   MqlRates r[];
   ArraySetAsSeries(r, false);
   int n = CopyRates(_Symbol, PERIOD_M1, 0, 45000, r);
   if(n < 1000) return false;
   int today = NYDay(nyNow);
   // agrupar sesiones previas (velas 9:30-15:56 NY)
   int sDay[]; int sStart[]; int sCount[]; int ns = 0, last = -1;
   int idxDay[]; ArrayResize(idxDay, n);
   for(int i = 0; i < n; i++)
   {
      datetime ny = NYOf(r[i].time);
      int m = NYMin(ny), d = NYDay(ny);
      idxDay[i] = -1;
      if(d >= today || m < OPEN_MIN || m >= FLAT_MIN) continue;
      if(d != last)
      {
         ArrayResize(sDay, ns + 1); ArrayResize(sStart, ns + 1); ArrayResize(sCount, ns + 1);
         sDay[ns] = d; sStart[ns] = i; sCount[ns] = 0; ns++; last = d;
      }
      sCount[ns - 1]++;
      idxDay[i] = ns - 1;
   }
   // válidas: empiezan a las 9:30 y tienen >= 350 velas
   int valid[]; int nv = 0;
   for(int k = 0; k < ns; k++)
      if(NYMin(NYOf(r[sStart[k]].time)) == OPEN_MIN && sCount[k] >= 350) { ArrayResize(valid, nv + 1); valid[nv++] = k; }
   if(nv < NOISE_LB) return false;
   for(int j = 0; j < 12; j++)
   {
      int c = 600 + 30 * j;
      double sum = 0; int cntv = 0;
      for(int v = nv - NOISE_LB; v < nv; v++)
      {
         int k = valid[v];
         double o = r[sStart[k]].open;
         for(int i = sStart[k]; i < sStart[k] + sCount[k] && i < n; i++)
         {
            if(idxDay[i] != k) continue;
            if(NYMin(NYOf(r[i].time)) == c) { sum += MathAbs(r[i].close / o - 1.0); cntv++; break; }
         }
      }
      sigma[j] = cntv > 0 ? sum / cntv : -1;
   }
   int lk = valid[nv - 1];
   double prevClose = r[sStart[lk] + sCount[lk] - 1].close;
   noiseUpRef = MathMax(todayOpen, prevClose);
   noiseLoRef = MathMin(todayOpen, prevClose);
   return true;
}

//+------------------------------------------------------------------+
//| Estrategias de apertura                                          |
//+------------------------------------------------------------------+
void ResetDay(int d)
{
   curDay = d; orb15Done = false; orb5Done = false; noiseReady = false; biasReady = false; biasDay = 0;
   for(int j = 0; j < 12; j++) { noiseChecked[j] = false; sigma[j] = -1; }
}

// segundos desde que se conoció la señal (minuto NY 'm' de hoy)
int AgeSec(datetime nyNow, int m) { return NYMin(nyNow) * 60 + (int)(nyNow % 60) - m * 60; }

void RunOpening(datetime nyNow)
{
   int nm = NYMin(nyNow);
   if(nm >= FLAT_MIN)
   {
      ClosePos(S_ORB15, "15:57"); ClosePos(S_ORB5, "15:57"); ClosePos(S_NOISE, "15:57");
      return;
   }
   if(nm < OPEN_MIN + 5) return;
   MqlRates b[]; int mins[];
   if(TodayBars(nyNow, b, mins) == 0 || mins[0] != OPEN_MIN) return;

   // ORB5: primera vela de 5 minutos
   if(InpUseORB5 && !orb5Done && nm >= OPEN_MIN + 5)
   {
      orb5Done = true;
      int cnt = 0; double o = 0, h = -DBL_MAX, l = DBL_MAX, c = 0;
      for(int i = 0; i < ArraySize(b); i++)
         if(mins[i] >= OPEN_MIN && mins[i] < OPEN_MIN + 5)
         { if(cnt == 0) o = b[i].open; h = MathMax(h, b[i].high); l = MathMin(l, b[i].low); c = b[i].close; cnt++; }
      if(cnt == 5 && h > l && MathAbs(c - o) >= ORB5_FLAT * (h - l) && AgeSec(nyNow, OPEN_MIN + 5) <= InpMaxSignalAgeSec)
      {
         int d = c > o ? 1 : -1;
         OpenTrade(S_ORB5, d, d > 0 ? l : h, 0, ORB5_TARGET, InpMaxSpreadOpen, "1.ª vela de 5 min");
      }
   }

   // ORB15: rango 9:30-9:45 y primera vela M5 que cierra fuera antes de 11:30
   if(InpUseORB15 && !orb15Done && nm >= ORB15_END + 5)
   {
      if(!biasReady) { biasDay = SMA50Bias(); biasReady = true; }
      int cnt = 0; double hi = -DBL_MAX, lo = DBL_MAX;
      for(int i = 0; i < ArraySize(b); i++)
         if(mins[i] >= OPEN_MIN && mins[i] < ORB15_END) { hi = MathMax(hi, b[i].high); lo = MathMin(lo, b[i].low); cnt++; }
      if(cnt < 13 || biasDay == 0) orb15Done = true;
      else
      {
         for(int blk = ORB15_END; blk < ORB_LIMIT && blk + 5 <= nm; blk += 5)
         {
            int k = -1;                               // última vela M1 existente del bloque
            for(int i = 0; i < ArraySize(b); i++) if(mins[i] >= blk && mins[i] < blk + 5) k = i;
            if(k < 0) continue;
            double c = b[k].close;
            int d = c > hi ? 1 : (c < lo ? -1 : 0);
            if(d == 0) continue;
            orb15Done = true;
            if(d * biasDay <= 0) { Print("[orb15] la ruptura va contra la media de 50 días: hoy no se opera"); break; }
            if(AgeSec(nyNow, blk + 5) > InpMaxSignalAgeSec) { Print("[orb15] señal vieja: no se opera"); break; }
            OpenTrade(S_ORB15, d, d > 0 ? lo : hi, 0, 0, InpMaxSpreadOpen, "ruptura del rango de 15 min");
            break;
         }
         if(nm >= ORB_LIMIT) orb15Done = true;
      }
   }

   // NOISE: revisiones cada 30 min de 10:00 a 15:30
   if(InpUseNoise)
   {
      if(!noiseReady && nm >= 600) noiseReady = PrepareNoise(nyNow, b[0].open);
      if(!noiseReady) return;
      for(int j = 0; j < 12; j++)
      {
         int c = 600 + 30 * j;
         if(noiseChecked[j] || nm < c) continue;
         noiseChecked[j] = true;
         if(AgeSec(nyNow, c) > InpMaxSignalAgeSec || sigma[j] < 0) continue;
         int k = FindMin(mins, c - 1);
         if(k < 0) continue;
         double px = b[k].close;
         double U = noiseUpRef * (1 + sigma[j]), L = noiseLoRef * (1 - sigma[j]);
         int pos; FindPos(S_NOISE, pos);
         if((pos > 0 && px < U) || (pos < 0 && px > L)) { if(ClosePos(S_NOISE, "vuelve a la banda")) pos = 0; }
         if(pos == 0)
         {
            int d = px > U ? 1 : (px < L ? -1 : 0);
            if(d != 0)
            {
               double unit = (U - L) / 2.0;
               OpenTrade(S_NOISE, d, px - d * NOISE_STOP * unit, 0, 0, InpMaxSpreadOpen, "fuera de la banda de ruido");
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| EMA 20/50 H1                                                     |
//+------------------------------------------------------------------+
void RunEMA()
{
   datetime bar = iTime(_Symbol, PERIOD_H1, 0);
   if(bar == 0 || bar == lastH1) return;
   double f[2], s[2], a[1];
   if(CopyBuffer(hFast, 0, 1, 2, f) != 2 || CopyBuffer(hSlow, 0, 1, 2, s) != 2 || CopyBuffer(hATR, 0, 1, 1, a) != 1) return;
   lastH1 = bar;
   if(TimeCurrent() - bar > InpMaxSignalAgeSec) return;   // llegamos tarde a esta vela
   int now  = f[1] > s[1] ? 1 : (f[1] < s[1] ? -1 : 0);
   int prev = f[0] > s[0] ? 1 : (f[0] < s[0] ? -1 : 0);
   int sig = (now > 0 && prev <= 0) ? 1 : ((now < 0 && prev >= 0) ? -1 : 0);
   if(sig == 0) return;
   int dir; FindPos(S_EMA, dir);
   if(dir == -sig && !ClosePos(S_EMA, "cruce contrario")) return;
   OpenTrade(S_EMA, sig, 0, EMA_STOPATR * a[0], EMA_TARGET, InpMaxSpreadEMA, "cruce EMA 20/50");
}

//+------------------------------------------------------------------+
int OnInit()
{
   if(InpRiskPct <= 0 || InpRiskPct > 2.0) { Print("Riesgo no válido (máx. 2 %)."); return INIT_PARAMETERS_INCORRECT; }
   if(InpOnlyDemo && !MQLInfoInteger(MQL_TESTER) && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   { Print("La cuenta no es DEMO y InpOnlyDemo=true: el EA no se ejecuta."); return INIT_FAILED; }
   hFast = iMA(_Symbol, PERIOD_H1, EMA_FAST, 0, MODE_EMA, PRICE_CLOSE);
   hSlow = iMA(_Symbol, PERIOD_H1, EMA_SLOW, 0, MODE_EMA, PRICE_CLOSE);
   hATR  = iATR(_Symbol, PERIOD_H1, 14);
   if(hFast == INVALID_HANDLE || hSlow == INVALID_HANDLE || hATR == INVALID_HANDLE) return INIT_FAILED;
   trade.SetDeviationInPoints(InpSlippagePoints);
   trade.SetTypeFillingBySymbol(_Symbol);
   lastH1 = iTime(_Symbol, PERIOD_H1, 0);              // no actuar sobre un cruce viejo al arrancar
   ResetDay(NYDay(NYOf(TimeCurrent())));
   EventSetTimer(5);
   Print("EA_Nasdaq_Cartera4 listo: orb15, orb5, noise, ema2050h1. Una operación por estrategia.");
   Tg(StringFormat("EA_Nasdaq_Cartera4 en marcha en %s (%s). Equity %.2f. Riesgo %.2f %% por operación.",
                   AccountInfoString(ACCOUNT_SERVER), AccountInfoInteger(ACCOUNT_TRADE_MODE) == ACCOUNT_TRADE_MODE_DEMO ? "DEMO" : "REAL",
                   AccountInfoDouble(ACCOUNT_EQUITY), InpRiskPct));
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   if(hFast != INVALID_HANDLE) IndicatorRelease(hFast);
   if(hSlow != INVALID_HANDLE) IndicatorRelease(hSlow);
   if(hATR  != INVALID_HANDLE) IndicatorRelease(hATR);
}

void Process()
{
   datetime ny = NYOf(TimeCurrent());
   int d = NYDay(ny);
   if(d != curDay) ResetDay(d);
   MqlDateTime t; TimeToStruct(ny, t);
   if(t.day_of_week >= 1 && t.day_of_week <= 5 && !IsHoliday(d) && (InpUseORB15 || InpUseORB5 || InpUseNoise))
      RunOpening(ny);
   if(InpUseEMA) RunEMA();
}

// Aviso de cada cierre (stop, objetivo, regla o fin del día) de las posiciones del EA
void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &req, const MqlTradeResult &res)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD || !HistoryDealSelect(trans.deal)) return;
   long mg = HistoryDealGetInteger(trans.deal, DEAL_MAGIC);
   if(mg <= InpMagicBase || mg > InpMagicBase + S_EMA) return;
   if(HistoryDealGetInteger(trans.deal, DEAL_ENTRY) != DEAL_ENTRY_OUT) return;
   double pnl = HistoryDealGetDouble(trans.deal, DEAL_PROFIT) + HistoryDealGetDouble(trans.deal, DEAL_SWAP)
              + HistoryDealGetDouble(trans.deal, DEAL_COMMISSION);
   long reason = HistoryDealGetInteger(trans.deal, DEAL_REASON);
   string why = reason == DEAL_REASON_SL ? "stop" : reason == DEAL_REASON_TP ? "objetivo" : "regla del EA";
   Tg(StringFormat("%s: CIERRA a %.2f por %s | resultado %.2f %s", SName((int)(mg - InpMagicBase)),
                   HistoryDealGetDouble(trans.deal, DEAL_PRICE), why, pnl, AccountInfoString(ACCOUNT_CURRENCY)));
}

void OnTick()  { Process(); }
void OnTimer() { Process(); }
//+------------------------------------------------------------------+
