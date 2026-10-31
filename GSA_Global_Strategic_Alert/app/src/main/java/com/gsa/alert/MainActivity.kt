package com.gsa.alert

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

private val Bg = Color(0xFF090E18)
private val Panel = Color(0xFF121C2B)
private val Muted = Color(0xFF91A0B5)
private val Red = Color(0xFFFF4D5E)
private val Amber = Color(0xFFFFB547)
private val Green = Color(0xFF39C58A)

data class AlertEvent(val id: String, val title: String, val summary: String,
    val source: String, val url: String, val level: Int, val published: String)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { GsaApp() }
    }
}

@Composable
fun GsaApp() {
    var events by remember { mutableStateOf(listOf<AlertEvent>()) }
    var status by remember { mutableStateOf("لم يتم الاتصال بالخادم بعد") }
    var loading by remember { mutableStateOf(false) }
    var selected by remember { mutableStateOf("ALL") }
    val scope = rememberCoroutineScope()

    suspend fun refresh() {
        loading = true
        status = "جارٍ تحديث البيانات..."
        val result = fetchEvents()
        events = result.first
        status = result.second
        loading = false
    }

    MaterialTheme(colorScheme = darkColorScheme(primary = Red, background = Bg, surface = Panel)) {
        Column(Modifier.fillMaxSize().background(Bg).padding(18.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("GSA", color = Red, fontSize = 13.sp, fontWeight = FontWeight.Bold, letterSpacing = 3.sp)
                    Text("GLOBAL STRATEGIC ALERT", color = Color.White, fontSize = 20.sp, fontWeight = FontWeight.ExtraBold)
                    Text("نظام الإنذار المبكر للأحداث العالمية", color = Muted, fontSize = 12.sp)
                }
                IconButton(onClick = { scope.launch { refresh() } }) {
                    Icon(Icons.Default.Refresh, contentDescription = "Refresh", tint = Color.White)
                }
            }
            Spacer(Modifier.height(18.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatusTile("مستوى الرصد", "عالمي", Green, Modifier.weight(1f))
                StatusTile("تنبيهات حرجة", events.size.toString(), Red, Modifier.weight(1f))
                StatusTile("حالة الاتصال", if (status.startsWith("متصل")) "متصل" else "غير متصل", Amber, Modifier.weight(1f))
            }
            Spacer(Modifier.height(16.dp))
            Text("مركز الأحداث الحرجة", color = Color.White, fontSize = 17.sp, fontWeight = FontWeight.Bold)
            Text(status, color = Muted, fontSize = 11.sp)
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected == "ALL", { selected = "ALL" }, label = { Text("الكل") })
                FilterChip(selected == "5", { selected = "5" }, label = { Text("المستوى 5") })
                FilterChip(selected == "4", { selected = "4" }, label = { Text("المستوى 4") })
            }
            Spacer(Modifier.height(8.dp))
            val visible = events.filter { selected == "ALL" || it.level.toString() == selected }
            if (visible.isEmpty()) {
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("لا توجد أحداث حرجة معروضة", color = Color.White, fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(6.dp))
                        Text("هذا لا يعني عدم وقوع أحداث؛ اربط التطبيق بخادم مراقبة فعّال.", color = Muted, fontSize = 12.sp)
                        Spacer(Modifier.height(12.dp))
                        Button(onClick = { scope.launch { refresh() } }, enabled = !loading) {
                            Text(if (loading) "جارٍ التحديث" else "تحديث الآن")
                        }
                    }
                }
            } else {
                LazyColumn(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(visible) { EventCard(it) }
                }
            }
        }
    }
}

@Composable
fun StatusTile(label: String, value: String, accent: Color, modifier: Modifier = Modifier) {
    Column(modifier.background(Panel, RoundedCornerShape(12.dp)).padding(11.dp)) {
        Text(label, color = Muted, fontSize = 10.sp)
        Spacer(Modifier.height(5.dp))
        Text(value, color = accent, fontWeight = FontWeight.Bold, fontSize = 14.sp)
    }
}

@Composable
fun EventCard(event: AlertEvent) {
    var expanded by remember { mutableStateOf(false) }
    val accent = if (event.level >= 5) Red else Amber
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = Panel),
        shape = RoundedCornerShape(14.dp)) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("LEVEL ${event.level}", color = accent, fontWeight = FontWeight.ExtraBold, fontSize = 11.sp)
                Spacer(Modifier.weight(1f))
                Text(event.published, color = Muted, fontSize = 10.sp)
            }
            Spacer(Modifier.height(8.dp))
            Text(event.title, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 15.sp)
            Spacer(Modifier.height(6.dp))
            Text(event.summary, color = Muted, fontSize = 12.sp, maxLines = if (expanded) 12 else 3)
            TextButton(onClick = { expanded = !expanded }) { Text(if (expanded) "عرض أقل" else "التفاصيل", color = accent) }
            Text("المصدر: ${event.source}", color = Muted, fontSize = 10.sp)
            Text(event.url, color = Color(0xFF79B8FF), fontSize = 10.sp, maxLines = 1)
        }
    }
}

private suspend fun fetchEvents(): Pair<List<AlertEvent>, String> = withContext(Dispatchers.IO) {
    try {
        val base = BuildConfig.API_BASE_URL.trimEnd('/')
        require(!base.contains("YOUR-BACKEND-HOST")) { "لم يتم ضبط عنوان الخادم في إعدادات البناء" }
        val client = OkHttpClient.Builder().callTimeout(20, TimeUnit.SECONDS).build()
        val request = Request.Builder().url("$base/events?min_level=4&limit=50").build()
        client.newCall(request).execute().use { response ->
            check(response.isSuccessful) { "HTTP ${response.code}" }
            val json = JSONObject(response.body?.string() ?: "{}")
            val array = json.optJSONArray("events")
            val list = buildList {
                if (array != null) for (i in 0 until array.length()) {
                    val o = array.getJSONObject(i)
                    add(AlertEvent(o.optString("id"), o.optString("title"), o.optString("summary"),
                        o.optString("source"), o.optString("url"), o.optInt("level"), o.optString("published")))
                }
            }
            Pair(list, "متصل بالخادم — تم جلب ${list.size} حدث")
        }
    } catch (e: Exception) {
        Pair(emptyList(), "تعذر الاتصال: ${e.message ?: "خطأ غير معروف"}")
    }
}
