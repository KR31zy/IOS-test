import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../../core/theme.dart';
import 'report_data.dart';

const chartColors = [blue, green, Color(0xff5478ab), Color(0xffe6a23c), Color(0xff7a66a5), Color(0xff48a7a1), Color(0xff9c674b)];

class MonthlyChart extends StatelessWidget {
  const MonthlyChart({super.key, required this.buckets});
  final List<MonthBucket> buckets;
  @override
  Widget build(BuildContext context) {
    final maxCount = buckets.fold<int>(1, (m, b) => math.max(m, b.count));
    final reduced = MediaQuery.disableAnimationsOf(context);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Semantics(
        label: 'Monthly record counts: ${buckets.map((b) => '${b.label} ${b.count}').join(', ')}',
        child: ExcludeSemantics(child: SizedBox(height: 105 + MediaQuery.textScalerOf(context).scale(14) * 3, child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: buckets.map((b) => Expanded(child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Column(mainAxisAlignment: MainAxisAlignment.end, children: [
              Text('${b.count}', style: TextStyle(fontWeight: FontWeight.w700, color: readableText(context))),
              const SizedBox(height: 4),
              TweenAnimationBuilder<double>(
                duration: reduced ? Duration.zero : const Duration(milliseconds: 550),
                tween: Tween(begin: 0, end: b.count / maxCount),
                builder: (context, fraction, child) => Container(
                  constraints: const BoxConstraints(maxWidth: 38),
                  height: fraction * 85 + (b.count > 0 ? 3 : 1),
                  decoration: BoxDecoration(gradient: brandGradient, borderRadius: BorderRadius.circular(6)),
                ),
              ),
              const SizedBox(height: 6),
              Text(b.label, style: Theme.of(context).textTheme.labelSmall, maxLines: 1),
            ]),
          ))).toList(),
        ))),
      ),
      const SizedBox(height: 6),
      Text('Calendar months • current month is incomplete', style: Theme.of(context).textTheme.bodySmall),
    ]);
  }
}

class SpeciesDonut extends StatelessWidget {
  const SpeciesDonut({super.key, required this.counts});
  final Map<String, int> counts;
  @override
  Widget build(BuildContext context) {
    final entries = counts.entries.toList();
    final total = counts.values.fold<int>(0, (a, b) => a + b);
    if (total == 0) return const Padding(padding: EdgeInsets.all(12), child: Text('No registered animals.'));
    final reduced = MediaQuery.disableAnimationsOf(context);
    return Column(children: [
      SizedBox(width: 168, height: 168, child: Stack(alignment: Alignment.center, children: [
        Semantics(label: 'Animal species distribution. Total $total animals.', child: TweenAnimationBuilder<double>(
          duration: reduced ? Duration.zero : const Duration(milliseconds: 650),
          tween: Tween(begin: 0, end: 1),
          builder: (context, progress, child) => CustomPaint(size: const Size.square(168), painter: _DonutPainter(entries.map((e) => e.value).toList(), progress)),
        )),
        Column(mainAxisSize: MainAxisSize.min, children: [Text('$total', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w800, color: readableText(context))), const Text('Animals')]),
      ])),
      const SizedBox(height: 12),
      for (var i = 0; i < entries.length; i++) Padding(padding: const EdgeInsets.symmetric(vertical: 5), child: Row(children: [
        Container(width: 12, height: 12, decoration: BoxDecoration(color: chartColors[i % chartColors.length], shape: BoxShape.circle)),
        const SizedBox(width: 8), Expanded(child: Text(entries[i].key)),
        Text('${entries[i].value}  •  ${(entries[i].value * 100 / total).toStringAsFixed(1)}%'),
      ])),
    ]);
  }
}

class _DonutPainter extends CustomPainter {
  _DonutPainter(this.values, this.progress);
  final List<int> values;
  final double progress;
  @override
  void paint(Canvas canvas, Size size) {
    final bounds = Offset.zero & size;
    final ring = bounds.deflate(14);
    final paint = Paint()..style = PaintingStyle.stroke..strokeWidth = 21;
    canvas.drawArc(ring, 0, math.pi * 2, false, paint..color = mint);
    final total = values.fold<int>(0, (a,b) => a+b);
    if (total == 0) return;
    double start = -math.pi / 2;
    for (var i = 0; i < values.length; i++) {
      final sweep = math.pi * 2 * values[i] / total * progress;
      canvas.drawArc(ring, start, sweep, false, paint..color = chartColors[i % chartColors.length]);
      start += sweep;
    }
  }
  @override
  bool shouldRepaint(covariant _DonutPainter oldDelegate) => progress != oldDelegate.progress || values.toString() != oldDelegate.values.toString();
}

/// Two measured, permission-filtered event series. No interpolation or demo data.
class ComparisonMonthlyChart extends StatelessWidget {
  const ComparisonMonthlyChart({super.key,required this.buckets,required this.firstLabel,required this.secondLabel});
  final List<ComparisonBucket> buckets;
  final String firstLabel,secondLabel;
  @override Widget build(BuildContext context) {
    final maxCount = math.max(1,buckets.fold<int>(0,(m,b)=>math.max(m,math.max(b.first,b.second))));
    final reduced=MediaQuery.disableAnimationsOf(context);
    Widget bar(int n,Color color)=>Row(children:[
      Expanded(child:TweenAnimationBuilder<double>(
        duration:reduced?Duration.zero:const Duration(milliseconds:420),
        tween:Tween(begin:0,end:n/maxCount),
        builder:(context,value,_)=>ClipRRect(borderRadius:BorderRadius.circular(5),
          child:LinearProgressIndicator(value:value,minHeight:10,color:color,backgroundColor:Theme.of(context).colorScheme.surfaceContainerHighest)))),
      const SizedBox(width:8),SizedBox(width:25,child:Text('$n',textAlign:TextAlign.end,style:Theme.of(context).textTheme.labelSmall)),
    ]);
    return Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
      Wrap(spacing:15,runSpacing:6,children:[
        _legend(firstLabel,blue),_legend(secondLabel,green),
      ]),const SizedBox(height:14),
      if(buckets.every((b)=>b.first==0&&b.second==0)) const Text('No comparison records in the last six calendar months.')
      else for(final bucket in buckets) Padding(padding:const EdgeInsets.only(bottom:12),child:Row(
        crossAxisAlignment:CrossAxisAlignment.center,children:[
          SizedBox(width:38,child:Text(bucket.label,style:Theme.of(context).textTheme.labelMedium)),
          Expanded(child:Column(children:[bar(bucket.first,blue),const SizedBox(height:5),bar(bucket.second,green)])),
        ])),
      Text('Event counts by calendar month, not animal prevalence or clinical outcomes.',style:Theme.of(context).textTheme.bodySmall),
    ]);
  }
  Widget _legend(String label,Color color)=>Row(mainAxisSize:MainAxisSize.min,children:[
    Container(width:11,height:11,decoration:BoxDecoration(color:color,borderRadius:BorderRadius.circular(3))),
    const SizedBox(width:6),Text(label),
  ]);
}

class PeriodComparisonChart extends StatelessWidget {
  const PeriodComparisonChart({super.key,required this.counts});
  final Map<String,(int,int)> counts;
  @override Widget build(BuildContext context) {
    final maxCount=math.max(1,counts.values.fold<int>(0,(n,p)=>math.max(n,math.max(p.$1,p.$2))));
    final reduced=MediaQuery.disableAnimationsOf(context);
    return Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
      Wrap(spacing:14,runSpacing:6,children:[_key('Previous 3 calendar months',blue),_key('Latest 3 calendar months',green)]),
      const SizedBox(height:14),
      if(counts.values.every((v)=>v.$1==0&&v.$2==0))const Text('No recent records to compare.'),
      for(final entry in counts.entries)Padding(padding:const EdgeInsets.only(bottom:14),child:Column(
        crossAxisAlignment:CrossAxisAlignment.start,children:[
          Text(entry.key,style:Theme.of(context).textTheme.titleSmall),const SizedBox(height:5),
          _bar(context,entry.value.$1,maxCount,blue,reduced),const SizedBox(height:4),
          _bar(context,entry.value.$2,maxCount,green,reduced),
        ])),
      Text('Partial months and API history limits can affect these counts.',style:Theme.of(context).textTheme.bodySmall),
    ]);
  }
  Widget _key(String label,Color color)=>Row(mainAxisSize:MainAxisSize.min,children:[
    Container(height:11,width:11,decoration:BoxDecoration(color:color,borderRadius:BorderRadius.circular(3))),const SizedBox(width:5),Text(label)]);
  Widget _bar(BuildContext c,int value,int maximum,Color color,bool reduced)=>Row(children:[
    Expanded(child:TweenAnimationBuilder<double>(duration:reduced?Duration.zero:const Duration(milliseconds:450),
      tween:Tween(begin:0,end:value/maximum),builder:(ctx,v,_)=>ClipRRect(borderRadius:BorderRadius.circular(5),
      child:LinearProgressIndicator(value:v,minHeight:9,color:color,backgroundColor:Theme.of(c).colorScheme.surfaceContainerHighest)))),
    const SizedBox(width:7),SizedBox(width:26,child:Text('$value',textAlign:TextAlign.end)),
  ]);
}
