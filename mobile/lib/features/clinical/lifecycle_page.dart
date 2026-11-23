import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/theme.dart';
import '../../screens/records.dart';
import '../../screens/extras.dart';
import '../../widgets/common.dart';
import 'lifecycle_data.dart';

class LifecyclePage extends StatefulWidget {
  const LifecyclePage({super.key,required this.api,required this.farm,required this.animal});
  final Api api;
  final RowData farm,animal;
  @override State<LifecyclePage> createState()=>_LifecyclePageState();
}
class _LifecyclePageState extends State<LifecyclePage> {
  String filter='all';
  int visibleLimit=50;
  @override Widget build(BuildContext context)=>DataPage(title:'Animal lifecycle',load:()async{
    final path=animalPath(widget.farm,widget.animal);
    final history=rows(await widget.api.get('$path/events'));
    final animals=rows(await widget.api.get('${farmPath(widget.farm)}/animals'));
    List<RowData> births=[];
    String? relationIssue;
    if(allowed(widget.farm,'breeding.observe')) {
      try {births=rows(await widget.api.get('${farmPath(widget.farm)}/events?category=birth'));}
      catch(e){relationIssue='Farm-wide birth links unavailable: $e';}
    }
    return [history,animals,births,relationIssue];
  },content:(c,data,reload){
    final history=LifecycleData(rows(data[0]));
    final animals={for(final a in rows(data[1])) '${a['id']}':a};
    final births=rows(data[2]);
    final parents=LifecycleData.parentIds('${widget.animal['id']}',births);
    final categories=history.events.map((e)=>e['category']).whereType<String>().toSet().toList()..sort();
    final selected=categories.contains(filter)?filter:'all';
    final visible=selected=='all'?history.events:history.category(selected);
    Widget heading(String t)=>Padding(padding:const EdgeInsets.only(top:18,bottom:8),child:Text(t,style:Theme.of(c).textTheme.titleLarge));
    Widget link(String id,String relation){final a=animals[id];return item(a==null?'Unavailable animal':pretty(a['name']),relation,icon:Icons.pets,onTap:a==null?null:()=>openPage(c,AnimalDetail(api:widget.api,farm:widget.farm,animal:a)));}
    return ListView(padding:const EdgeInsets.all(16),children:[
      Container(padding:const EdgeInsets.all(20),decoration:BoxDecoration(gradient:brandGradient,borderRadius:BorderRadius.circular(24)),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text(pretty(widget.animal['name']),style:const TextStyle(color:Colors.white,fontSize:27,fontWeight:FontWeight.bold)),Text('${pretty(widget.animal['tag'])} · ${pretty(widget.animal['species'])}',style:const TextStyle(color:Colors.white)),const SizedBox(height:12),Text('${history.events.length} returned records',style:const TextStyle(color:Colors.white,fontSize:16))])),
      if(widget.api.offline)const Text('Offline snapshot — not live clinical information.'),
      const Padding(padding:EdgeInsets.symmetric(vertical:12),child:Text('Historical records and measured values only. A confirmation record does not establish current pregnancy. Check the original event and seek veterinary confirmation when needed.')),
      heading('Latest recorded events'),
      for(final cat in ['health','reproduction','breeding','pregnancy','birth'])if(history.latest(cat)!=null)
        eventTile(c,widget.api,widget.farm,history.latest(cat)!,widget.animal,reload),
      if(allowed(widget.farm,'reproduction.view'))item('Reproductive cycle analysis','Server-calculated intervals and estimates',icon:Icons.timeline,onTap:()=>openPage(c,CyclePage(api:widget.api,farm:widget.farm,animal:widget.animal))),
      if(allowed(widget.farm,'breeding.observe'))...[
        heading('Recorded family relationships'),
        if(data[3]!=null)Text('${data[3]}'),
        if(births.length>=500)const Text('Farm birth history may be incomplete (500-record server limit).'),
        if(parents.isEmpty&&history.offspringIds.isEmpty)const Text('No accessible linked relatives in the returned records.'),
        for(final id in parents)link(id,'Recorded mother'),
        for(final id in history.offspringIds)link(id,'Registered offspring'),
      ],
      if(allowed(widget.farm,'health.view'))...[
        heading('Longitudinal health measurements'),
        ObservationTrend(title:'Weight (kg)',points:history.series('health','weight_kg',kind:'examination')),
        ObservationTrend(title:'Temperature (°C)',points:history.series('health','temperature_c',kind:'examination')),
        ObservationTrend(title:'Body condition score',points:history.series('health','body_condition_score',kind:'examination')),
        const Text('Values are displayed without species-specific diagnostic thresholds.'),
      ],
      if(allowed(widget.farm,'reproduction.view'))...[
        heading('Hormone measurements'),
        if(history.hormoneSeries.isEmpty)const Text('No comparable recorded hormone values.'),
        for(final entry in history.hormoneSeries.entries)ObservationTrend(title:entry.key,points:entry.value),
        const Text('Separated by analyte, units, sample, method and laboratory.'),
      ],
      heading('Clinical timeline'),
      DropdownButtonFormField<String>(key:ValueKey(selected),initialValue:selected,isExpanded:true,decoration:const InputDecoration(labelText:'Filter history'),items:['all',...categories].map((v)=>DropdownMenuItem(value:v,child:Text(pretty(v)))).toList(),onChanged:(v)=>setState((){filter=v??'all';visibleLimit=50;})),
      if(visible.isEmpty)const MessagePane('No records in this view.'),
      ...visible.take(visibleLimit).map((e)=>eventTile(c,widget.api,widget.farm,e,widget.animal,reload)),
      if(visible.length>visibleLimit)TextButton(onPressed:()=>setState(()=>visibleLimit+=50),child:Text('Show more (${visible.length-visibleLimit} remaining)')),
    ]);
  });
}

class ObservationTrend extends StatelessWidget {
  const ObservationTrend({super.key,required this.title,required this.points});
  final String title;
  final List<Observation> points;
  @override Widget build(BuildContext context){
    final recent=points.length>30?points.sublist(points.length-30):points;
    return Card(child:Padding(padding:const EdgeInsets.all(14),child:Column(crossAxisAlignment:CrossAxisAlignment.stretch,children:[
      Text(title,style:Theme.of(context).textTheme.titleMedium),
      if(recent.isEmpty)const Text('No recorded measurements.')else ...[
        Text('Latest: ${recent.last.value.toStringAsFixed(2)} · ${shortDate(recent.last.at)}'),
        if(recent.length>1) SizedBox(height:130,child:Semantics(label:'Trend of ${recent.length} recorded measurements, exact values below',child:CustomPaint(painter:_TrendPainter(recent)))),
        ExpansionTile(tilePadding:EdgeInsets.zero,title:Text('View ${recent.length} measurements'),children:recent.reversed.map((p)=>ListTile(dense:true,title:Text(shortDate(p.at)),trailing:Text(p.value.toStringAsFixed(2)))).toList()),
        if(points.length>30)const Text('Showing latest 30 measurements.'),
      ],
    ])));
  }
}
class _TrendPainter extends CustomPainter {
  _TrendPainter(this.points);
  final List<Observation> points;
  @override void paint(Canvas canvas,Size size){
    if(points.length<2||size.width<=16||size.height<=16)return;
    var lo=points.first.value,hi=lo;
    for(final p in points){if(p.value<lo)lo=p.value;if(p.value>hi)hi=p.value;}
    final start=points.first.at.millisecondsSinceEpoch,span=points.last.at.millisecondsSinceEpoch-start;
    final line=Path();
    final dots=<Offset>[];
    for(var i=0;i<points.length;i++){
      final p=points[i];
      final x=8+(span==0?i/(points.length-1):(p.at.millisecondsSinceEpoch-start)/span)*(size.width-16);
      final y=hi==lo?size.height/2:8+(hi-p.value)/(hi-lo)*(size.height-16);
      if(i==0){line.moveTo(x.toDouble(),y.toDouble());}else{line.lineTo(x.toDouble(),y.toDouble());} dots.add(Offset(x.toDouble(),y.toDouble()));
    }
    canvas.drawPath(line,Paint()..color=green..strokeWidth=2..style=PaintingStyle.stroke);
    for(final dot in dots){canvas.drawCircle(dot,3,Paint()..color=blue);}
  }
  @override bool shouldRepaint(covariant _TrendPainter oldDelegate)=>oldDelegate.points!=points;
}
