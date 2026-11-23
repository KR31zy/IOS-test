import 'package:flutter/material.dart';

// Existing AniRepro 360 brand tokens. Do not change logos or primary palette.
const blue=Color(0xff1565c0), navy=Color(0xff0d2b45), green=Color(0xff0b8457), bright=Color(0xff16a36a), mint=Color(0xffe8f5ee), canvas=Color(0xfff5f8fa);
const brandGradient=LinearGradient(colors:[navy,blue,green],begin:Alignment.topLeft,end:Alignment.bottomRight);

ThemeData appTheme()=>ThemeData(
  useMaterial3:true,
  colorScheme:ColorScheme.fromSeed(seedColor:blue,primary:blue,secondary:green,surface:Colors.white),
  scaffoldBackgroundColor:canvas,
  appBarTheme:const AppBarTheme(backgroundColor:canvas,foregroundColor:navy,centerTitle:false),
  inputDecorationTheme:InputDecorationTheme(filled:true,fillColor:const Color(0xffedf3f4),
    border:OutlineInputBorder(borderRadius:BorderRadius.circular(24),borderSide:BorderSide.none),
    focusedBorder:OutlineInputBorder(borderRadius:BorderRadius.circular(24),borderSide:const BorderSide(color:green,width:1.5)),
    contentPadding:const EdgeInsets.symmetric(horizontal:18,vertical:16)),
  filledButtonTheme:FilledButtonThemeData(style:FilledButton.styleFrom(minimumSize:const Size(0,52),shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(28)))),
  cardTheme:CardThemeData(color:Colors.white,elevation:0,margin:const EdgeInsets.symmetric(vertical:5),shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(20),side:const BorderSide(color:Color(0xffe2e9ed)))),
  navigationBarTheme:const NavigationBarThemeData(backgroundColor:Colors.white,indicatorColor:mint),
);

ThemeData appDarkTheme() {
  const surface = Color(0xff182936);
  const base = Color(0xff0d1d29);
  final colors = ColorScheme.fromSeed(
    seedColor:blue, brightness:Brightness.dark,
    primary:const Color(0xff91c1ff),secondary:const Color(0xff67d8aa),
    surface:surface,onSurface:const Color(0xfff0f6fa),
  );
  return ThemeData(
    useMaterial3:true,brightness:Brightness.dark,colorScheme:colors,
    scaffoldBackgroundColor:base,
    appBarTheme:const AppBarTheme(backgroundColor:base,foregroundColor:Colors.white,centerTitle:false),
    inputDecorationTheme:InputDecorationTheme(filled:true,fillColor:const Color(0xff253949),
      border:OutlineInputBorder(borderRadius:BorderRadius.circular(24),borderSide:BorderSide.none),
      focusedBorder:OutlineInputBorder(borderRadius:BorderRadius.circular(24),borderSide:BorderSide(color:colors.secondary,width:1.5)),
      contentPadding:const EdgeInsets.symmetric(horizontal:18,vertical:16)),
    filledButtonTheme:FilledButtonThemeData(style:FilledButton.styleFrom(minimumSize:const Size(0,52),shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(28)))),
    cardTheme:CardThemeData(color:surface,elevation:0,margin:const EdgeInsets.symmetric(vertical:5),shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(20),side:const BorderSide(color:Color(0xff304654)))),
    navigationBarTheme:NavigationBarThemeData(backgroundColor:surface,indicatorColor:colors.primary.withValues(alpha:.22)),
  );
}

Color readableText(BuildContext context)=>Theme.of(context).colorScheme.onSurface;
