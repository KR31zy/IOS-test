import 'dart:io';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

/// No animal, account, farm or treatment data is written to the OS notification store.
class NativeAlerts {
  NativeAlerts._();
  static final instance=NativeAlerts._();
  final _plugin=FlutterLocalNotificationsPlugin();
  Future<void>? _initialized;
  Future<void> init()=>_initialized??=_init();
  Future<void> _init() async {
    if(!Platform.isAndroid&&!Platform.isIOS)throw UnsupportedError('Device alerts are available on Android and iOS.');
    tzdata.initializeTimeZones();
    await _plugin.initialize(const InitializationSettings(
      android:AndroidInitializationSettings('ic_stat_anirepro'),
      iOS:DarwinInitializationSettings(requestAlertPermission:false,requestBadgePermission:false,requestSoundPermission:false)));
  }
  Future<bool> permission() async {
    await init();
    if(Platform.isAndroid)return await _plugin.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()?.requestNotificationsPermission()??false;
    return await _plugin.resolvePlatformSpecificImplementation<IOSFlutterLocalNotificationsPlugin>()?.requestPermissions(alert:true,badge:false,sound:true)??false;
  }
  static const _details=NotificationDetails(android:AndroidNotificationDetails('farm_reminders_v1','Farm reminders',channelDescription:'Private reminders to review recorded farm dates',importance:Importance.defaultImportance,visibility:NotificationVisibility.private),iOS:DarwinNotificationDetails());
  Future<void> replace(List<DateTime> times) async {
    await init();await _plugin.cancelAll();
    try{
      for(var i=0;i<times.length;i++){
        await _plugin.zonedSchedule(1000+i,'AniRepro 360','Review recorded farm reminders in the app.',tz.TZDateTime.from(times[i],tz.UTC),_details,androidScheduleMode:AndroidScheduleMode.inexactAllowWhileIdle);
      }
    }catch(_){await _plugin.cancelAll();rethrow;}
  }
  Future<int> count() async {await init();return (await _plugin.pendingNotificationRequests()).length;}
  Future<void> cancel() async {if(!Platform.isAndroid&&!Platform.isIOS)return;await init();await _plugin.cancelAll();}
  Future<void> inboxAlert() async {await init();await _plugin.show(998,'AniRepro 360','New farm activity. Open the app to review.',_details);}
  Future<void> testAlert() async {await init();await _plugin.show(999,'AniRepro 360','Device notifications are enabled.',_details);}
}
