import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Local device preference. It does not change the farm or server configuration.
class AppAppearance extends ValueNotifier<ThemeMode> {
  AppAppearance._() : super(ThemeMode.system);
  static final AppAppearance instance = AppAppearance._();
  static const _storage = FlutterSecureStorage();
  static const _key = 'anirepro-appearance:v1';

  Future<void> restore() async {
    try {
      final saved = await _storage.read(key: _key);
      value = switch (saved) {
        'light' => ThemeMode.light,
        'dark' => ThemeMode.dark,
        _ => ThemeMode.system,
      };
    } catch (_) {
      value = ThemeMode.system;
    }
  }

  Future<void> choose(ThemeMode mode) async {
    await _storage.write(key: _key, value: mode.name);
    value = mode;
  }
}
