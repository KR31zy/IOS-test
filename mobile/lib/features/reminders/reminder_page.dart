import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/theme.dart';
import '../../screens/records.dart';
import '../../widgets/common.dart';
import 'native_alerts.dart';
import 'reminder_data.dart';
import 'push_service.dart';

class ReminderPage extends StatefulWidget {
  const ReminderPage({super.key,required this.api,required this.farm});
  final Api api; final RowData farm;
  @override State<ReminderPage> createState()=>_ReminderPageState();
}
class _ReminderPageState extends State<ReminderPage>{
  String filter='all'; TimeOfDay time=const TimeOfDay(hour:8,minute:0);
  bool dayBefore=true,busy=false; FarmReminder? estimate; String? estimateAnimal;
  int? scheduled; String? note;
  Api get api=>widget.api;
  Future<List<dynamic>> load() async {
    final path=farmPath(widget.farm);
    return Future.wait([api.get('$path/animals'),api.get('$path/events')]);
  }
  Future<void> run(Future<void> Function() action) async {
    if(busy)return;setState(()=>busy=true);
    try{await action();}catch(e){if(mounted)toast(context,e);}finally{if(mounted)setState(()=>busy=false);}
  }
  Future<void> cycle(List<RowData> animals) async {
    final a=animals.where((a)=>a['id']==estimateAnimal).firstOrNull;if(a==null)return;
    await run(()async{
      final data=obj(await api.get('${animalPath(widget.farm,a)}/cycle-summary'));
      if(!mounted)return;setState(()=>estimate=estrusReminder(a,data));
      if(estimate==null)toast(context,'No supported estimate from recorded cycle history.');
    });
  }
  Future<void> schedule() async {
    if(api.offline){toast(context,'Connect and refresh this farm before scheduling device reminders.');return;}
    if(!await confirm(context,'Replace existing device reminders with these recorded dates for this farm? Alerts are generic, may be delayed and do not track clinical completion automatically.'))return;
    if(!mounted)return;
    await run(()async{
      final identity=api.user?['id'];
      final revision=api.workspaceRevision;
      final memberships=rows(await api.get('/api/farms'));
      if(!memberships.any((f)=>f['id']==widget.farm['id'] && allowed(f,'animals.view')))throw StateError('Farm access changed. Reopen your workspace.');
      final fresh=await load();
      if(!mounted||api.workspaceRevision!=revision||api.offline||!api.signedIn||api.user?['id']!=identity)throw StateError('Session or connectivity changed; refresh first.');
      final verified=recordedReminders(rows(fresh[1]),rows(fresh[0]));
      if(estimate!=null&&estimateAnimal!=null){
        final a=rows(fresh[0]).where((a)=>a['id']==estimateAnimal).firstOrNull;
        if(a!=null){final s=obj(await api.get('${animalPath(widget.farm,a)}/cycle-summary'));final e=estrusReminder(a,s);if(e!=null)verified.add(e);}
      }
      if(!mounted||api.workspaceRevision!=revision||api.offline||api.user?['id']!=identity)throw StateError('Session or connectivity changed.');
      // Schedule from fresh confirmed records, not from an old on-screen list.
      final times=alertTimes(verified,DateTime.now(),hour:time.hour,minute:time.minute,dayBefore:dayBefore);
      if(!await NativeAlerts.instance.permission())throw StateError('Notification permission denied. Enable it in phone settings.');
      if(!mounted||api.workspaceRevision!=revision||!api.signedIn||api.user?['id']!=identity)return;
      await NativeAlerts.instance.replace(times);
      if(api.workspaceRevision!=revision||!api.signedIn||api.user?['id']!=identity){await NativeAlerts.instance.cancel();return;}
      if(mounted)setState((){scheduled=times.length;note='Device reminders replaced; dates are a snapshot. Refresh after record changes.';});
    });
  }
  @override Widget build(BuildContext context)=>DataPage(title:'Farm reminders',load:load,content:(c,data,reload){
    final animals=rows(data[0]),events=rows(data[1]);
    final all=recordedReminders(events,animals);if(estimate!=null&&animals.any((a)=>a['id']==estimateAnimal))all.add(estimate!);
    final today=day(DateTime.now()); all.sort((a,b)=>a.due.compareTo(b.due));
    final visible=all.where((r)=>filter=='all'||(filter=='past'&&r.due.isBefore(today))||(filter=='today'&&r.due==today)||(filter=='upcoming'&&r.due.isAfter(today))).toList();
    return ListView(padding:const EdgeInsets.all(16),children:[
      Container(padding:const EdgeInsets.all(20),decoration:BoxDecoration(gradient:brandGradient,borderRadius:BorderRadius.circular(24)),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[const Icon(Icons.calendar_month,color:Colors.white,size:32),const SizedBox(height:8),Text('${widget.farm['name']}',style:const TextStyle(color:Colors.white,fontSize:22,fontWeight:FontWeight.bold)),Text('${all.length} recorded dates • ${all.where((r)=>r.due==today).length} today • ${all.where((r)=>r.due.isBefore(today)).length} past',style:const TextStyle(color:Colors.white))])),
      if(api.offline)const Padding(padding:EdgeInsets.all(8),child:Text('Offline snapshot — may be out of date.')),
      const Padding(padding:EdgeInsets.symmetric(vertical:12),child:Text('Recorded dates are not proof of outstanding care. Verify clinical history and current plans.')),
      if(events.length>=500)const Text('Partial history: server returns up to 500 visible events.'),
      if(allowed(widget.farm,'reproduction.view')) ...[
        Text('Estrus observation estimate',style:Theme.of(c).textTheme.titleMedium),
        DropdownButtonFormField<String>(initialValue:animals.any((a)=>a['id']==estimateAnimal)?estimateAnimal:null,isExpanded:true,decoration:const InputDecoration(labelText:'Choose animal'),items:animals.map((a)=>DropdownMenuItem(value:'${a['id']}',child:Text('${a['name']} • ${a['tag']}',overflow:TextOverflow.ellipsis))).toList(),onChanged:busy?null:(v)=>setState((){estimateAnimal=v;estimate=null;})),
        TextButton(onPressed:busy||estimateAnimal==null?null:()=>cycle(animals),child:const Text('Load recorded cycle estimate')),
      ],
      Wrap(spacing:8,children:['all','today','upcoming','past'].map((f)=>ChoiceChip(label:Text(pretty(f)),selected:filter==f,onSelected:(_)=>setState(()=>filter=f))).toList()),
      if(visible.isEmpty)const MessagePane('No recorded dates in this view.'),
      ...visible.map((r)=>Card(child:ListTile(leading:Icon(r.estimated?Icons.timeline:Icons.event_note,color:r.due.isBefore(today)?Colors.orange:green),title:Text(r.label),subtitle:Text('${r.animal}\n${dateLabel(r.due)}${r.estimated?' • estimate, not confirmation':''}'),isThreeLine:true))),
      const Divider(),Text('Device notifications',style:Theme.of(c).textTheme.titleLarge),
      ListTile(title:const Text('Reminder time (phone local time)'),trailing:Text(time.format(c)),onTap:busy?null:()async{final t=await showTimePicker(context:c,initialTime:time);if(t!=null&&mounted)setState(()=>time=t);}),
      SwitchListTile(title:const Text('Also remind one day before'),value:dayBefore,onChanged:busy?null:(v)=>setState(()=>dayBefore=v)),
      BrandButton('Schedule next 30 days',busy:busy,action:api.offline?null:schedule),
      TextButton(onPressed:busy?null:()=>run(()async{if(!await NativeAlerts.instance.permission())throw StateError('Notification permission denied.');await NativeAlerts.instance.testAlert();}),child:const Text('Test device notification')),
      TextButton(onPressed:busy?null:()=>run(()async{await NativeAlerts.instance.cancel();if(mounted)setState((){scheduled=0;note='Device alerts cleared.';});}),child:const Text('Clear device alerts')),
      TextButton(onPressed:busy?null:()=>run(()async{final n=await NativeAlerts.instance.count();if(mounted)setState(()=>scheduled=n);}),child:const Text('Check scheduled alerts')),
      if(scheduled!=null)Text('$scheduled pending device alerts'),if(note!=null)Text(note!),
      const Text('Alerts contain no clinical data. They may be delayed by phone settings, and must be replaced after plans or farm access change.'),
      const Divider(),TextButton.icon(onPressed:()=>openPage(c,PushSettingsPage(api:api)),icon:const Icon(Icons.notifications_active_outlined),label:const Text('Remote push settings')),
    ]);
  });
}
