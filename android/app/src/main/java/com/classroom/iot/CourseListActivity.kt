package com.classroom.iot

import android.content.Intent
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.classroom.iot.databinding.ActivityCourseListBinding
import com.classroom.iot.model.CourseInfo
import com.classroom.iot.network.ApiClient
import com.classroom.iot.util.PreferenceManager
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.time.temporal.ChronoUnit

class CourseListActivity : AppCompatActivity() {
    private lateinit var b: ActivityCourseListBinding
    private lateinit var api: ApiClient
    private var selDate = ""
    private var refreshJob: Job? = null

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        b = ActivityCourseListBinding.inflate(layoutInflater)
        setContentView(b.root)
        b.rvCourses.layoutManager = LinearLayoutManager(this)
        val p = (application as ClassroomIoTApp).prefs
        api = ApiClient("http://${p.serverIp}:${p.serverPort}")
        b.toolbar.title = "板书查看"
        b.toolbar.setNavigationOnClickListener { finish() }
        loadDates()
    }

    override fun onResume() {
        super.onResume()
        if (selDate.isNotEmpty()) startAutoRefresh()
    }

    override fun onPause() {
        super.onPause()
        stopAutoRefresh()
    }

    override fun onDestroy() {
        super.onDestroy()
        stopAutoRefresh()
    }

    private fun startAutoRefresh() {
        stopAutoRefresh()
        refreshJob = lifecycleScope.launch {
            while (true) {
                fetchAndShowCourses()
                delay(3000) // 每 3 秒静默刷新一次课程状态
            }
        }
    }

    private fun stopAutoRefresh() {
        refreshJob?.cancel()
        refreshJob = null
    }

    private fun loadDates() {
        lifecycleScope.launch {
            try {
                val r = api.getDates()
                if (r.dates.isEmpty()) {
                    b.tvEmpty.visibility = View.VISIBLE
                    b.rvCourses.visibility = View.GONE
                    return@launch
                }
                selDate = if (r.dates.contains(java.time.LocalDate.now().toString())) java.time.LocalDate.now().toString() else r.dates.first()
                buildChips(r.dates)
            } catch (e: Exception) {
                Toast.makeText(this@CourseListActivity, "失败", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun buildChips(dates: List<String>) {
        b.dateSelector.removeAllViews()
        val today = java.time.LocalDate.now()
        for (d in dates) {
            val dd = java.time.LocalDate.parse(d)
            val diff = ChronoUnit.DAYS.between(dd, today)
            val txt = when (diff) {
                0L -> "今天"
                1L -> "昨天"
                else -> dd.format(java.time.format.DateTimeFormatter.ofPattern("MM/dd"))
            }
            val c = com.google.android.material.chip.Chip(this).apply {
                text = txt
                isClickable = true
                isCheckable = true
                textSize = 13f
                if (d == selDate) isChecked = true
            }
            c.setOnClickListener {
                selDate = d
                for (i in 0 until b.dateSelector.childCount)
                    (b.dateSelector.getChildAt(i) as com.google.android.material.chip.Chip).isChecked = false
                c.isChecked = true
                // 切换日期时立即重启刷新器
                stopAutoRefresh()
                startAutoRefresh()
            }
            b.dateSelector.addView(c)
        }
    }

    private fun fetchAndShowCourses() {
        lifecycleScope.launch {
            try {
                val r = api.getCourses(selDate)
                if (r.courses.isEmpty()) {
                    b.tvEmpty.visibility = View.VISIBLE
                    b.rvCourses.visibility = View.GONE
                    b.rvCourses.adapter = null
                } else {
                    b.tvEmpty.visibility = View.GONE
                    b.rvCourses.visibility = View.VISIBLE
                    val adapter = b.rvCourses.adapter as? CAdapter
                    if (adapter != null) {
                        // 复用现有 Adapter，只更新数据，防止列表闪烁
                        adapter.updateData(r.courses)
                    } else {
                        b.rvCourses.adapter = CAdapter(r.courses) { co ->
                            if (co.isAccessible()) {
                                startActivity(Intent(this@CourseListActivity, CourseDetailActivity::class.java).apply {
                                    putExtra("d", selDate)
                                    putExtra("i", co.index)
                                    putExtra("n", co.name)
                                    putExtra("s", co.start)
                                    putExtra("e", co.end)
                                    putExtra("st", co.state)
                                })
                            }
                        }
                    }
                }
            } catch (_: Exception) {
                // 静默处理刷新时的网络波动，不弹 Toast
            }
        }
    }

    inner class CAdapter(private var l: List<CourseInfo>, private val cb: (CourseInfo) -> Unit) : RecyclerView.Adapter<CAdapter.VH>() {

        // 新增：供外部实时刷新数据的方法
        fun updateData(newList: List<CourseInfo>) {
            l = newList
            notifyDataSetChanged()
        }

        inner class VH(v: View) : RecyclerView.ViewHolder(v)

        override fun onCreateViewHolder(p: ViewGroup, v: Int) = VH(layoutInflater.inflate(R.layout.item_course, p, false))

        override fun onBindViewHolder(h: VH, pos: Int) {
            val co = l[pos]
            val tvN = h.itemView.findViewById<TextView>(R.id.tvCourseName)
            val tvT = h.itemView.findViewById<TextView>(R.id.tvCourseTime)
            val tvS = h.itemView.findViewById<TextView>(R.id.tvCourseState)
            val card = h.itemView.findViewById<com.google.android.material.card.MaterialCardView>(R.id.cardCourse)

            tvN.text = co.name
            tvT.text = "${co.start} - ${co.end}"
            tvS.text = co.stateText()

            val (c, bg) = when (co.state) {
                "running" -> Color.parseColor("#E65100") to Color.parseColor("#FFF3E0")
                "finished" -> Color.parseColor("#2E7D32") to Color.parseColor("#E8F5E9")
                else -> Color.parseColor("#9E9E9E") to Color.parseColor("#F5F5F5")
            }
            tvS.setTextColor(c)
            val shape = GradientDrawable()
            shape.setColor(bg)
            shape.cornerRadius = 40f
            tvS.background = shape

            val acc = co.isAccessible()
            card.alpha = if (acc) 1f else 0.4f
            card.isClickable = acc
            if (acc) card.setOnClickListener { cb(co) }
        }

        override fun getItemCount() = l.size
    }
}
