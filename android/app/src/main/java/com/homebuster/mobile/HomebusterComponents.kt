package com.homebuster.mobile

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage

@Composable
fun HomebusterTopBar(
    subtitle: String? = null,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null
) {
    Surface(color = Color(0xFF151923), tonalElevation = 0.dp) {
        Row(
            Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(Modifier.weight(1f)) {
                Text("Homebuster", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.ExtraBold)
                if (!subtitle.isNullOrBlank()) Text(subtitle, color = HbMuted, style = MaterialTheme.typography.bodySmall)
            }
            if (actionLabel != null && onAction != null) TextButton(onClick = onAction) { Text(actionLabel, color = HbAccent) }
        }
    }
    HorizontalDivider(color = HbLine)
}

@Composable
fun HomebusterScreenHeader(title: String, onBack: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(bottom = 14.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        TextButton(onClick = onBack, contentPadding = PaddingValues(horizontal = 4.dp, vertical = 4.dp)) {
            Text("‹", style = MaterialTheme.typography.headlineMedium, color = HbAccent)
        }
        Spacer(Modifier.width(4.dp))
        Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun HomebusterPanel(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit
) {
    val clickable = if (onClick == null) modifier else modifier.clickable(onClick = onClick)
    Card(
        modifier = clickable,
        colors = CardDefaults.cardColors(containerColor = HbPanel),
        border = BorderStroke(1.dp, HbLine),
        shape = RoundedCornerShape(14.dp)
    ) {
        Column(Modifier.fillMaxWidth().padding(16.dp), content = content)
    }
}

@Composable
fun HomebusterMetaChip(text: String, color: Color = HbMuted) {
    Surface(color = HbPanel2, shape = RoundedCornerShape(50)) {
        Text(text, color = color, style = MaterialTheme.typography.bodySmall, modifier = Modifier.padding(horizontal = 9.dp, vertical = 4.dp))
    }
}

@Composable
fun HomebusterErrorCard(message: String) {
    Card(colors = CardDefaults.cardColors(containerColor = HbPanel), border = BorderStroke(1.dp, HbDanger)) {
        Text(message, color = HbDanger, modifier = Modifier.padding(12.dp))
    }
}

@Composable
fun HomebusterEmptyState(message: String) {
    HomebusterPanel { Text(message, color = HbMuted) }
}

@Composable
fun HomebusterMovieCard(group: MovieGroup, onClick: () -> Unit) {
    val movie = group.primary
    Card(
        Modifier.fillMaxWidth().clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = HbPanel),
        border = BorderStroke(1.dp, HbLine),
        shape = RoundedCornerShape(14.dp)
    ) {
        if (movie.posterUrl != null) {
            AsyncImage(
                model = movie.posterUrl,
                contentDescription = movie.title,
                modifier = Modifier.fillMaxWidth().aspectRatio(2f / 3f).clip(RoundedCornerShape(topStart = 14.dp, topEnd = 14.dp)),
                contentScale = ContentScale.Crop
            )
        } else {
            Box(
                Modifier.fillMaxWidth().aspectRatio(2f / 3f).background(Color(0xFF0B0E14)),
                contentAlignment = Alignment.Center
            ) { Text("🎬", style = MaterialTheme.typography.displaySmall, color = HbMuted) }
        }
        Column(Modifier.padding(12.dp)) {
            Text(movie.title, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.height(4.dp))
            movie.year?.let { Text(it.toString(), color = HbMuted, style = MaterialTheme.typography.bodySmall) }
            Text(group.formatsSummary, color = HbAccent, style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}
