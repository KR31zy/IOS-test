import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:anirepro360_mobile/features/clinical/module_ui.dart';
import 'package:anirepro360_mobile/features/clinical/animal_ui.dart';
import 'package:anirepro360_mobile/screens/records.dart';
import 'package:anirepro360_mobile/core/api.dart';

void main() {
  final events = <RowData>[
    {'kind':'service','animal_id':'a','status':'observed','occurred_at':'2026-01-01T10:00:00Z','payload':{'method':'natural'}},
    {'kind':'service','animal_id':'b','status':'completed','occurred_at':'2026-03-01T10:00:00Z','payload':{'method':'artificial_insemination'}},
    {'kind':'service','animal_id':'a','status':'completed','occurred_at':'2026-02-01T10:00:00Z'},
  ];
  test('all server categories have a module style', () {
    expect(moduleStyles.keys.toSet(), kinds.keys.toSet());
  });
  test('filters combine animal, method, status and search', () {
    expect(filterEvents(events,animalId:'a',metric:'method:natural',status:'observed',search:'ALPHA',animals:{'a':{'name':'Alpha'}}), [events.first]);
    expect(filterEvents(events,metric:'method:artificial_insemination'), [events[1]]);
    expect(filterEvents(events,status:'completed'), [events[1],events[2]]);
    expect(events.first['animal_id'],'a');
  });
  test('missing payload does not count as a service method', () {
    expect(matchesMetric(events.last,'method:natural'),isFalse);
  });
  testWidgets('metric tile exposes real count and toggles filter', (tester) async {
    String? picked;
    await tester.pumpWidget(MaterialApp(home:Scaffold(body:MetricTiles(style:moduleStyles['breeding']!,events:events,selected:'all',onSelect:(v)=>picked=v))));
    expect(find.text('3'),findsOneWidget);
    await tester.tap(find.text('Natural mating'));
    expect(picked,'method:natural');
  });
  testWidgets('missing weight is not presented as zero', (tester) async {
    await tester.pumpWidget(const MaterialApp(home:Scaffold(body:AnimalHeader(animal:{'name':'A','tag':'1','species':'cattle'}))));
    expect(find.text('Not recorded'),findsOneWidget);
  });
}
