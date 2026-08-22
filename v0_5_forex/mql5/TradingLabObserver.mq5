// TradingLAB V0.5 observer-only indicator.
// This is not an Expert Advisor and intentionally contains no trade or network
// operation. A human may attach it to an MT5 chart for visual inspection only.
#property copyright "TradingLAB local research"
#property version   "0.5.0"
#property indicator_chart_window
#property indicator_buffers 1
#property indicator_plots   1
#property indicator_label1  "Research SMA"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrOrange

input int InpSmaPeriod = 200;
double SmaBuffer[];

int OnInit()
  {
   if(InpSmaPeriod < 2)
      return(INIT_PARAMETERS_INCORRECT);
   SetIndexBuffer(0,SmaBuffer,INDICATOR_DATA);
   PlotIndexSetInteger(0,PLOT_DRAW_BEGIN,InpSmaPeriod-1);
   return(INIT_SUCCEEDED);
  }

int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < InpSmaPeriod)
      return(0);
   int first = prev_calculated > 0 ? prev_calculated-1 : InpSmaPeriod-1;
   for(int index=first; index<rates_total; index++)
     {
      double sum = 0.0;
      for(int offset=0; offset<InpSmaPeriod; offset++)
         sum += close[index-offset];
      SmaBuffer[index] = sum/InpSmaPeriod;
     }
   return(rates_total);
  }
