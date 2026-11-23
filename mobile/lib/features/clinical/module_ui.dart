import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/theme.dart';

/// Presentation metadata only: category and kind values remain API keys.
class ModuleStyle {
  const ModuleStyle(this.title, this.description, this.icon, this.color,
      this.metrics, this.action, this.empty);
  final String title, description, action, empty;
  final IconData icon;
  final Color color;
  final List<(String, String, IconData)> metrics;
}

const moduleStyles = <String, ModuleStyle>{
  'health': ModuleStyle('Animal health', 'Track examinations, treatments and preventive care.', Icons.monitor_heart_outlined, blue, [
    ('examination', 'Examinations', Icons.medical_services_outlined),
    ('vaccination', 'Vaccinations', Icons.vaccines_outlined),
    ('medication', 'Medications', Icons.medication_outlined),
    ('disease', 'Disease records', Icons.healing_outlined),
  ], 'Add health record', 'No health records match your filters.'),
  'reproduction': ModuleStyle('Reproductive monitoring', 'Observe fertility, cycles and reproductive findings.', Icons.timeline, green, [
    ('estrus', 'Heat observations', Icons.water_drop_outlined),
    ('ovulation', 'Ovulation records', Icons.timeline),
    ('follicle', 'Follicle records', Icons.biotech_outlined),
    ('hormone', 'Hormone records', Icons.science_outlined),
  ], 'Add observation', 'No reproductive records match your filters.'),
  'breeding': ModuleStyle('Breeding services', 'Document natural mating and artificial insemination.', Icons.hub_outlined, blue, [
    ('service', 'Service records', Icons.hub_outlined),
    ('method:natural', 'Natural mating', Icons.pets),
    ('method:artificial_insemination', 'Insemination', Icons.science_outlined),
  ], 'Record breeding service', 'No breeding services match your filters.'),
  'pregnancy': ModuleStyle('Pregnancy monitoring', 'Review assessments, confirmations and outcomes.', Icons.favorite_outline, green, [
    ('assessment', 'Assessments', Icons.fact_check_outlined),
    ('confirmation', 'Confirmation records', Icons.verified_outlined),
    ('follow_up', 'Follow-up records', Icons.event_note_outlined),
    ('outcome', 'Outcome records', Icons.assignment_turned_in_outlined),
  ], 'Add pregnancy record', 'No pregnancy records match your filters.'),
  'birth': ModuleStyle('Births & offspring', 'Document deliveries and newborn follow-up.', Icons.child_friendly, green, [
    ('delivery', 'Delivery records', Icons.child_friendly),
    ('offspring_follow_up', 'Offspring follow-up', Icons.fact_check_outlined),
  ], 'Record birth or follow-up', 'No birth records match your filters.'),
  'task': ModuleStyle('Farm tasks', 'Review scheduled activities and record completion.', Icons.task_alt, blue, [
    ('examination', 'Examination tasks', Icons.medical_services_outlined),
    ('vaccination', 'Vaccination tasks', Icons.vaccines_outlined),
    ('pregnancy_check', 'Pregnancy checks', Icons.event_available_outlined),
    ('follow_up', 'Follow-up tasks', Icons.event_note_outlined),
  ], 'Add task record', 'No task records match your filters.'),
};

Map<String, dynamic> eventPayload(RowData event) {
  final p = event['payload'];
  return p is Map ? Map<String, dynamic>.from(p) : {};
}

bool matchesMetric(RowData event, String metric) {
  if (metric.startsWith('method:')) {
    return event['kind'] == 'service' && eventPayload(event)['method'] == metric.substring(7);
  }
  return event['kind'] == metric;
}

List<RowData> filterEvents(List<RowData> events, {String? animalId,
    String metric = 'all', String status = 'all', String search = '',
    Map<String, RowData> animals = const {}}) {
  final q = search.trim().toLowerCase();
  final visible = events.where((e) {
    final a = animals['${e['animal_id']}'];
    final combined = '${pretty(e['kind'])} ${pretty(e['status'])} ${a?['name'] ?? ''} ${a?['tag'] ?? ''}'.toLowerCase();
    return (animalId == null || '${e['animal_id']}' == animalId) &&
        (metric == 'all' || matchesMetric(e, metric)) &&
        (status == 'all' || e['status'] == status) && combined.contains(q);
  }).toList();
  DateTime time(RowData e) => serverTime(e['occurred_at']) ?? DateTime.fromMillisecondsSinceEpoch(0, isUtc: true);
  visible.sort((a,b) => time(b).compareTo(time(a)));
  return visible;
}

class ModuleHero extends StatelessWidget {
  const ModuleHero({super.key, required this.style, required this.count});
  final ModuleStyle style;
  final int count;
  @override Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(gradient: LinearGradient(colors: [navy, style.color], begin: Alignment.topLeft, end: Alignment.bottomRight), borderRadius: BorderRadius.circular(24)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [CircleAvatar(backgroundColor: Colors.white24, foregroundColor: Colors.white, child: Icon(style.icon)), const SizedBox(width: 12), Expanded(child: Text(style.title, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800, fontSize: 21)))]),
      const SizedBox(height: 12), Text(style.description, style: const TextStyle(color: Colors.white)),
      const SizedBox(height: 16), Text('$count', style: const TextStyle(color: Colors.white, fontSize: 34, fontWeight: FontWeight.w800)),
      const Text('Visible records for selected animal scope', style: TextStyle(color: Colors.white)),
    ]),
  );
}

class MetricTiles extends StatelessWidget {
  const MetricTiles({super.key, required this.style, required this.events, required this.selected, required this.onSelect});
  final ModuleStyle style;
  final List<RowData> events;
  final String selected;
  final ValueChanged<String> onSelect;
  @override Widget build(BuildContext context) => LayoutBuilder(builder: (context, box) {
    final columns = box.maxWidth >= 660 ? 4 : box.maxWidth >= 280 ? 2 : 1;
    final width = (box.maxWidth - (columns-1)*10)/columns;
    return Wrap(spacing: 10, runSpacing: 10, children: style.metrics.map((m) {
      final active = selected == m.$1;
      final total = events.where((e) => matchesMetric(e,m.$1)).length;
      return SizedBox(width: width, child: Semantics(selected: active, button: true, child: Material(
        color: active ? mint : Theme.of(context).colorScheme.surface, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16), side: BorderSide(color: active ? green : const Color(0xffe2e9ed))),
        child: InkWell(borderRadius: BorderRadius.circular(16), onTap: () => onSelect(active ? 'all' : m.$1), child: Padding(padding: const EdgeInsets.all(14), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(m.$3, color: style.color), const SizedBox(height: 8), Text('$total', style: TextStyle(fontSize: 26, fontWeight: FontWeight.w800, color: active ? navy : readableText(context))), Text(m.$2),
        ]))),
      )));
    }).toList());
  });
}

class RecordStatus extends StatelessWidget {
  const RecordStatus(this.status, {super.key});
  final Object? status;
  @override Widget build(BuildContext context) {
    final positive = status == 'confirmed' || status == 'completed';
    final caution = status == 'suspected' || status == 'predicted';
    final color = positive ? green : caution ? const Color(0xffa36c21) : readableText(context);
    return DecoratedBox(decoration: BoxDecoration(color: color.withValues(alpha: .09), borderRadius: BorderRadius.circular(20)), child: Padding(padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5), child: Text(pretty(status), style: TextStyle(color: color, fontWeight: FontWeight.w600, fontSize: 12))));
  }
}

/// Date only where possible; the detail page retains the original timestamp.
String recordDay(Object? value) {
  final date = DateTime.tryParse('$value')?.toLocal();
  return date == null ? pretty(value) : '${date.year}-${date.month.toString().padLeft(2,'0')}-${date.day.toString().padLeft(2,'0')}';
}
