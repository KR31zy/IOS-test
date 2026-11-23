import 'package:flutter/material.dart';
import '../../core/api.dart';
import '../../core/theme.dart';

class AnimalCard extends StatelessWidget {
  const AnimalCard({super.key, required this.animal, required this.onTap});
  final RowData animal;
  final VoidCallback onTap;
  @override Widget build(BuildContext context) => Card(child: InkWell(
    borderRadius: BorderRadius.circular(20), onTap: onTap,
    child: Padding(padding: const EdgeInsets.all(14), child: Row(children: [
      const CircleAvatar(radius: 27, backgroundColor: mint, foregroundColor: green, child: Icon(Icons.pets, size: 26)), const SizedBox(width: 12),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(pretty(animal['name']), style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w700)),
        Text('ID: ${pretty(animal['tag'])}'), const SizedBox(height: 6),
        Wrap(spacing: 8, runSpacing: 4, children: [Text(pretty(animal['species']), style: const TextStyle(color: green, fontWeight: FontWeight.w600)), Text(pretty(animal['sex'])), if ('${animal['breed'] ?? ''}'.isNotEmpty) Text(pretty(animal['breed']))]),
      ])), Icon(Icons.chevron_right, color: readableText(context)),
    ])),
  ));
}

class AnimalHeader extends StatelessWidget {
  const AnimalHeader({super.key, required this.animal});
  final RowData animal;
  @override Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(20), decoration: BoxDecoration(gradient: brandGradient, borderRadius: BorderRadius.circular(24)),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [const CircleAvatar(radius: 30, backgroundColor: Colors.white24, foregroundColor: Colors.white, child: Icon(Icons.pets, size: 30)), const SizedBox(width: 14), Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Text(pretty(animal['name']), style: const TextStyle(color: Colors.white, fontSize: 24, fontWeight: FontWeight.w800)), Text('ID: ${pretty(animal['tag'])}', style: const TextStyle(color: Colors.white))]))]),
      const SizedBox(height: 16), Wrap(spacing: 20, runSpacing: 10, children: [
        _property('Species', pretty(animal['species'])), _property('Sex', pretty(animal['sex'])),
        _property('Breed', pretty(animal['breed'])), _property('Recorded weight', animal['weight_kg'] == null ? 'Not recorded' : '${animal['weight_kg']} kg'),
      ]),
    ]),
  );
  Widget _property(String name, String value) => Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [Text(name, style: const TextStyle(color: Colors.white70, fontSize: 12)), Text(value, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600))]);
}
