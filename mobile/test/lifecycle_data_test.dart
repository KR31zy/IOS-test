import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/core/api.dart';
import 'package:anirepro360_mobile/features/clinical/lifecycle_data.dart';
RowData record(String time,String category,String kind,RowData payload)=>{'occurred_at':time,'category':category,'kind':kind,'payload':payload};
void main(){
  test('trends use actual numeric values sorted by recorded date',(){
    final d=LifecycleData([
      record('2026-11-19T09:00:00Z','health','examination',{'weight_kg':42}),
      record('2026-11-18T09:00:00Z','health','examination',{'weight_kg':40}),
      record('2026-11-17T09:00:00Z','health','examination',{'weight_kg':'invalid'}),
      record('bad date','health','examination',{'weight_kg':39}),
      record('2026-11-20T09:00:00Z','health','medication',{'weight_kg':99}),
    ]);
    expect(d.series('health','weight_kg',kind:'examination').map((x)=>x.value),[40,42]);
  });
  test('different hormone methods and units stay separate',(){
    RowData h(String unit,String assay,num value)=>record('2026-11-19T09:00:00Z','reproduction','hormone',{'hormone_type':'P4','hormone_unit':unit,'sample_type':'serum','assay_method':assay,'laboratory':'lab','hormone_value':value});
    expect(LifecycleData([h('ng/ml','A',3),h('ng/ml','B',2),h('nmol/l','A',10)]).hormoneSeries.length,3);
  });
  test('family links rely on actual registered offspring IDs',(){
    final events=[record('2026-11-19T09:00:00Z','birth','delivery',{'offspring_animal_id':'child','mother_animal_id':'mother'}),record('2026-11-19T10:00:00Z','birth','delivery',{'offspring_tag':'only-a-tag'})];
    expect(LifecycleData(events).offspringIds,{'child'});
    expect(LifecycleData.parentIds('child',events),{'mother'});
    expect(LifecycleData.parentIds('other',events),isEmpty);
  });
  test('legacy UTC and explicit offset represent the same instant',(){
    expect(serverTime('2026-11-19T09:00:00')!.toUtc(), serverTime('2026-11-19T12:00:00+03:00')!.toUtc());
  });
}
