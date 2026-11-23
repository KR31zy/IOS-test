import '../../core/api.dart';

/// Aggregates only the records returned by the current farm's API.
class ReportData {
  const ReportData(this.events, this.animals);
  final List<RowData> events, animals;

  Map<String, int> get species => _group(animals, 'species');
  Map<String, int> get categories => _group(events, 'category');
  bool get possiblyCapped => events.length >= 500;

  static Map<String, int> _group(List<RowData> data, String field) {
    final counts = <String, int>{};
    for (final row in data) {
      final key = row[field]?.toString().trim() ?? '';
      final label = key.isEmpty ? 'Unknown' : pretty(key);
      counts.update(label, (v) => v + 1, ifAbsent: () => 1);
    }
    final sorted = counts.entries.toList()..sort((a, b) {
      final countOrder = b.value.compareTo(a.value);
      return countOrder == 0 ? a.key.compareTo(b.key) : countOrder;
    });
    return Map.fromEntries(sorted);
  }

  /// Six calendar months, including current month; no invented measurements.
  List<MonthBucket> monthly(DateTime now, {String? category}) {
    final local = now.toLocal();
    final start = DateTime(local.year, local.month - 5);
    final buckets = List.generate(6, (i) => MonthBucket(DateTime(start.year, start.month + i), 0));
    for (final row in events) {
      if (category != null && row['category'] != category) continue;
      final date = serverTime(row['occurred_at'])?.toLocal();
      if (date == null || date.isBefore(start) || date.isAfter(local)) continue;
      final i = (date.year - start.year) * 12 + date.month - start.month;
      if (i >= 0 && i < buckets.length) {
        buckets[i] = MonthBucket(buckets[i].month, buckets[i].count + 1);
      }
    }
    return buckets;
  }
}

class MonthBucket {
  const MonthBucket(this.month, this.count);
  final DateTime month;
  final int count;
  String get label => const ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][month.month - 1];
}

/// Comparisons count only events actually supplied by the authorized farm API.
/// Neither omitted older records nor unsynchronized drafts are extrapolated.
class ComparisonBucket {
  const ComparisonBucket(this.month,this.first,this.second);
  final DateTime month;
  final int first, second;
  String get label => const ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][month.month-1];
}

extension ReportComparisons on ReportData {
  List<ComparisonBucket> compareMonthly(DateTime now,{required String first, required String second}) {
    final left = monthly(now,category:first);
    final right = monthly(now,category:second);
    return List.generate(left.length,(i)=>ComparisonBucket(left[i].month,left[i].count,right[i].count));
  }
  Map<String,(int,int)> compareThreeMonthPeriods(DateTime now,Iterable<String> selected) {
    final output=<String,(int,int)>{};
    for(final category in selected) {
      final months=monthly(now,category:category);
      output[category]=(
        months.take(3).fold<int>(0,(sum,b)=>sum+b.count),
        months.skip(3).fold<int>(0,(sum,b)=>sum+b.count),
      );
    }
    return output;
  }
}
