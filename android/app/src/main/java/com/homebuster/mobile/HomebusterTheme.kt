package com.homebuster.mobile

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.Shapes
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

val HbBackground = Color(0xFF101218)
val HbPanel = Color(0xFF191D26)
val HbPanel2 = Color(0xFF222837)
val HbText = Color(0xFFEEF1F7)
val HbMuted = Color(0xFF9CA6B8)
val HbLine = Color(0xFF30384A)
val HbAccent = Color(0xFF7AA2FF)
val HbPrimary = Color(0xFF345FC1)
val HbDanger = Color(0xFFFF6B6B)
val HbGood = Color(0xFF62D49D)
val HbWarning = Color(0xFFF4C66B)

private val HomebusterColorScheme = darkColorScheme(
    primary = HbPrimary,
    onPrimary = Color.White,
    secondary = HbAccent,
    background = HbBackground,
    onBackground = HbText,
    surface = HbPanel,
    onSurface = HbText,
    surfaceVariant = HbPanel2,
    onSurfaceVariant = HbMuted,
    outline = HbLine,
    error = HbDanger
)

private val HomebusterShapes = Shapes(
    small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(14.dp),
    large = RoundedCornerShape(14.dp)
)

@Composable
fun HomebusterTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = HomebusterColorScheme,
        shapes = HomebusterShapes,
        content = content
    )
}
