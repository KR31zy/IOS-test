import '../../core/api.dart';

DateTime? dateOnly(Object? value) {
  if (value is! String || !RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(value)) return null;
  final d = DateTime.tryParse(value);
  if (d == null || d.toIso8601String().substring(0, 10) != value) return null;
  return d;
}
DateTime day(DateTime d) => DateTime(d.year,d.month,d.day);
String dateLabel(DateTime d) => '${d.year.toString().padLeft(4,'0')}-${d.month.toString().padLeft(2,'0')}-${d.day.toString().padLeft(2,'0')}';
class FarmReminder {
  const FarmReminder(this.id,this.animal,this.category,this.label,this.due,{this.estimated=false});
  final String id,animal,category,label;
  final DateTime due;
  final bool estimated;
}
/// Dates are recorded plans, not proof of outstanding treatment or a diagnosis.
/// The source feed is capped; do not infer completion from missing records.
List<FarmReminder> recordedReminders(List<RowData> events,List<RowData> animals) {
  final names={for(final a in animals) '${a['id']}':'${a['name']} • ${a['tag']}'};
  final result=<FarmReminder>[];
  final seen=<String>{};
  for(final e in events){
    final id='${e['id']}', animal=names['${e['animal_id']}'];
    if(animal==null || e['id']==null || !seen.add(id))continue;
    final p=e['payload']; if(p is! Map)continue;
    final category='${e['category']}', kind='${e['kind']}';
    void add(String key,String label,{bool estimated=false}){
      final due=dateOnly(p[key]);if(due==null)return;
      result.add(FarmReminder('$id:$key',animal,category,label,due,estimated:estimated));
    }
    if(category=='task' && !['completed','cancelled','canceled'].contains(e['status'])) add('due_date','Task: ${p['title']??pretty(kind)}');
    if(category=='health' && ['vaccination','medication','disease','follow_up'].contains(kind)) add('next_due_date',kind=='vaccination'?'Vaccination follow-up':kind=='medication'?'Medication follow-up':'Health follow-up');
    if(category=='breeding' && kind=='service')add('planned_pregnancy_check_date','Planned pregnancy check');
    if(category=='pregnancy' && ['assessment','confirmation','follow_up'].contains(kind)){
      add('next_due_date','Pregnancy follow-up');
      add('estimated_delivery_date','Recorded delivery estimate',estimated:true);
    }
  }
  result.sort((a,b)=>a.due.compareTo(b.due));return result;
}
FarmReminder? estrusReminder(RowData animal,RowData summary){
  final due=dateOnly(summary['estimated_next_estrus']);
  if(due==null||summary['estimate_status']!='prediction_not_confirmed'||summary['animal_id']!=animal['id'])return null;
  return FarmReminder('estrus:${animal['id']}','${animal['name']} • ${animal['tag']}','reproduction','Estimated next estrus — observe only',due,estimated:true);
}
/// At most 30 calendar-day alerts; no past-date alarm storms.
List<DateTime> alertTimes(Iterable<FarmReminder> records,DateTime now,{required int hour,required int minute,required bool dayBefore}){
  final dates=<String,DateTime>{};
  for(final r in records){
    for(final offset in dayBefore?[0,1]:[0]){
      final d=DateTime(r.due.year,r.due.month,r.due.day-offset,hour,minute);
      if(d.isAfter(now)&&!d.isAfter(now.add(const Duration(days:30)))) dates[dateLabel(d)]=d;
    }
  }
  return dates.values.toList()..sort();
}
