package com.anydaf.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

private val LightColors = lightColorScheme(
    primary = AppBlue,
    onPrimary = androidx.compose.ui.graphics.Color.White,
    primaryContainer = AppBlueLight,
    onPrimaryContainer = AppBlue,
    secondary = Brown600,
    onSecondary = androidx.compose.ui.graphics.Color.White,
    tertiary = Gold,
    background = Surface,
    onBackground = OnSurface,
    surface = Surface,
    onSurface = OnSurface,
)

private val DarkColors = darkColorScheme(
    primary = AppBlueLight,
    onPrimary = AppBlueDark,
    primaryContainer = AppBlueDark,
    onPrimaryContainer = AppBlueLight,
    secondary = Brown800,
    onSecondary = androidx.compose.ui.graphics.Color.White,
    tertiary = Gold,
    background = SurfaceDark,
    onBackground = OnSurfaceDark,
    surface = SurfaceDark,
    onSurface = OnSurfaceDark,
)

@Composable
fun AnyDafTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colorScheme = if (darkTheme) DarkColors else LightColors

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
