import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/features/analytics/report_data.dart';

void main() {
  test('groups real rows without adding sample data', () {
    final data = ReportData([], [{'species':'cattle'}, {'species':'goat'}, {'species':'cattle'}]);
    expect(data.species, {'cattle':2, 'goat':1});
    expect(data.categories, isEmpty);
  });
  test('monthly records respect dates, categories and calendar year boundaries', () {
    final now = DateTime(2026, 2, 15, 12);
    final data = ReportData([
      {'category':'health', 'occurred_at':'2025-10-03T11:00:00'},
      {'category':'health', 'occurred_at':'2026-02-01T11:00:00'},
      {'category':'birth', 'occurred_at':'2026-02-02T11:00:00'},
      {'category':'health', 'occurred_at':'2026-02-20T11:00:00'},
      {'category':'health', 'occurred_at':'bad-date'},
      {'category':'health', 'occurred_at':'2025-01-01T11:00:00'},
    ], []);
    expect(data.monthly(now).map((e)=>e.count).toList(), [0,1,0,0,0,2]);
    expect(data.monthly(now, category:'health').map((e)=>e.count).toList(), [0,1,0,0,0,1]);
    expect(data.monthly(now).first.label, 'Sep');
  });
  test('marks the 500-record server limit as possibly incomplete', () {
    expect(ReportData(List.generate(500, (_)=>{'category':'health'}), []).possiblyCapped, true);
    expect(ReportData([], []).possiblyCapped, false);
  });
}
