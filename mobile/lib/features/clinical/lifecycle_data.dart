import '../../core/api.dart';

/// Read-only summaries of the returned, permission-filtered event history.
/// Dates are observations, never a diagnosis or a calculated due date.
class Observation {
  const Observation(this.at, this.value);
  final DateTime at;
  final double value;
}

class LifecycleData {
  LifecycleData(Iterable<RowData> input) : events = input.toList() {
    events.sort((a,b) => (_at(b) ?? DateTime.fromMillisecondsSinceEpoch(0, isUtc:true))
        .compareTo(_at(a) ?? DateTime.fromMillisecondsSinceEpoch(0,isUtc:true)));
  }
  final List<RowData> events;
  static DateTime? _at(RowData e) => serverTime(e['occurred_at'])?.toUtc();
  static RowData payload(RowData e) => e['payload'] is Map ? obj(e['payload']) : {};
  List<RowData> category(String value) => events.where((e)=>e['category']==value).toList();
  RowData? latest(String categoryName) => category(categoryName).firstOrNull;
  List<Observation> series(String categoryName, String field, {String? kind}) {
    final result=<Observation>[];
    for(final e in category(categoryName)) {
      if(kind!=null && e['kind']!=kind)continue;
      final v=payload(e)[field], at=_at(e);
      if(v is num && v.isFinite && at!=null)result.add(Observation(at,v.toDouble()));
    }
    return result.reversed.toList();
  }
  /// Hormone values with incompatible analytes or units must not be combined.
  Map<String,List<Observation>> get hormoneSeries {
    final result=<String,List<Observation>>{};
    for(final e in category('reproduction').reversed) {
      if(e['kind']!='hormone')continue;
      final p=payload(e), at=_at(e), v=p['hormone_value'];
      final type='${p['hormone_type']??''}'.trim(), unit='${p['hormone_unit']??''}'.trim();
      if(type.isEmpty||unit.isEmpty||v is! num||!v.isFinite||at==null)continue;
      final sample='${p['sample_type']??''}'.trim(), assay='${p['assay_method']??''}'.trim(), lab='${p['laboratory']??''}'.trim();
      result.putIfAbsent('$type ($unit) · $sample · $assay · $lab',()=>[]).add(Observation(at,v.toDouble()));
    }
    return result;
  }
  Set<String> get offspringIds => category('birth').where((e)=>e['kind']=='delivery')
    .map((e)=>payload(e)['offspring_animal_id']).whereType<String>().where((s)=>s.isNotEmpty).toSet();
  static Set<String> parentIds(String animalId, Iterable<RowData> farmEvents) => farmEvents
    .where((e)=>e['category']=='birth'&&e['kind']=='delivery'&&payload(e)['offspring_animal_id']==animalId)
    .map((e)=>payload(e)['mother_animal_id']).whereType<String>().where((s)=>s.isNotEmpty).toSet();
}
