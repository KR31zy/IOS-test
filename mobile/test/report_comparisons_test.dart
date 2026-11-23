import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/features/analytics/report_data.dart';

void main() {
  test('monthly series compares real events without inventing counts', () {
    final data = ReportData([
      {'category':'health','occurred_at':'2026-06-01T10:00:00Z'},
      {'category':'health','occurred_at':'2026-07-03T10:00:00Z'},
      {'category':'reproduction','occurred_at':'2026-07-04T10:00:00Z'},
      {'category':'health','occurred_at':'2026-09-05T10:00:00Z'},
      {'category':'reproduction','occurred_at':'2026-10-05T10:00:00Z'},
      {'category':'health','occurred_at':'2026-11-22T10:00:00Z'}, // future
    ], []);
    final months = data.compareMonthly(DateTime(2026,11,21,12),first:'health',second:'reproduction');
    expect(months.map((m)=>m.first).toList(),[1,1,0,1,0,0]);
    expect(months.map((m)=>m.second).toList(),[0,1,0,0,1,0]);
    final periods = data.compareThreeMonthPeriods(DateTime(2026,11,21,12),['health','reproduction']);
    expect(periods['health'],(2,1));
    expect(periods['reproduction'],(1,1));
  });
  test('missing chart data remains zero, not synthetic data', () {
    final data=ReportData([],[]);
    expect(data.compareMonthly(DateTime(2026,11,21),first:'health',second:'breeding').every((m)=>m.first==0&&m.second==0),isTrue);
  });
}
