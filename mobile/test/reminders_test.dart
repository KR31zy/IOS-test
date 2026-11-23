import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/features/reminders/reminder_data.dart';
import 'package:anirepro360_mobile/core/api.dart';
void main(){
  final animals=<RowData>[{'id':'a','name':'Cow A','tag':'001'}];
  RowData event(String id,String category,String kind,RowData payload,{String status='observed',String animal='a'})=>{'id':id,'animal_id':animal,'category':category,'kind':kind,'status':status,'payload':payload};
  test('strict calendar dates reject rollover and timestamps',(){expect(dateOnly('2026-02-30'),isNull);expect(dateOnly('2026-11-19T00:00:00Z'),isNull);expect(dateOnly('2028-02-29'),DateTime(2028,2,29));});
  test('recorded follow ups and recorded delivery estimates only',(){final reminders=recordedReminders([
    event('1','health','vaccination',{'next_due_date':'2026-11-20'},status:'completed'),
    event('2','pregnancy','confirmation',{'estimated_delivery_date':'2026-12-01'}),
    event('3','breeding','service',{'planned_pregnancy_check_date':'2026-11-21'}),
    event('4','task','examination',{'due_date':'2026-11-22'},status:'completed'),
    event('5','health','medication',{'next_due_date':'2026-11-23'},animal:'hidden'),
    event('1','health','vaccination',{'next_due_date':'2026-11-20'}),
    event('6','pregnancy','confirmation',{'estimated_conception_date':'2026-01-01'}),
  ],animals);expect(reminders.map((r)=>r.id),['1:next_due_date','3:planned_pregnancy_check_date','2:estimated_delivery_date']);expect(reminders.last.estimated,isTrue);});
  test('estrus only from matching supported server estimate',(){final a=animals.single;expect(estrusReminder(a,{'animal_id':'a','estimate_status':'insufficient_or_inapplicable_history','estimated_next_estrus':'2026-11-20'}),isNull);expect(estrusReminder(a,{'animal_id':'other','estimate_status':'prediction_not_confirmed','estimated_next_estrus':'2026-11-20'}),isNull);expect(estrusReminder(a,{'animal_id':'a','estimate_status':'prediction_not_confirmed','estimated_next_estrus':'2026-11-20'})?.estimated,isTrue);});
  test('one alert per day, optional day-before, no past or beyond horizon',(){final now=DateTime(2026,11,19,9);final times=alertTimes([
    FarmReminder('a','a','health','x',DateTime(2026,11,21)),FarmReminder('b','a','health','y',DateTime(2026,11,21)),FarmReminder('c','a','health','z',DateTime(2026,11,19)),FarmReminder('d','a','health','z',DateTime(2027,1,2))
  ],now,hour:8,minute:0,dayBefore:true);expect(times,[DateTime(2026,11,20,8),DateTime(2026,11,21,8)]);});
}
