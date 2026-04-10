package com.classroom.iot

import android.net.ConnectivityManager
import android.net.NetworkRequest
import android.os.Bundle
import android.view.View
import android.widget.SeekBar
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import coil.load
import com.classroom.iot.databinding.ActivityCourseDetailBinding
import com.classroom.iot.network.ApiClient
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

class CourseDetailActivity : AppCompatActivity() {
    private lateinit var b: ActivityCourseDetailBinding
    private lateinit var api: ApiClient
    private lateinit var dateStr: String
    private var cIdx = 0
    private var cState = ""
    private var curType = "multimedia"
    private var imgs: List<String> = emptyList()
    private var curI = 0
    private var manualScroll = false
    private var pollJob: Job? = null
    private var isOfflineDialogShowing = false

    override fun onCreate(s: Bundle?) {
        super.onCreate(s)
        b = ActivityCourseDetailBinding.inflate(layoutInflater)
        setContentView(b.root)
        dateStr = intent.getStringExtra("d") ?: return
        cIdx = intent.getIntExtra("i", 0)
        val n = intent.getStringExtra("n") ?: ""
        val st = intent.getStringExtra("s") ?: ""
        val en = intent.getStringExtra("e") ?: ""
        cState = intent.getStringExtra("st") ?: "finished"

        val p = (application as ClassroomIoTApp).prefs
        api = ApiClient("http://${p.serverIp}:${p.serverPort}", p.token ?: "")

        b.toolbar.title = "$n $st-$en"
        b.toolbar.setNavigationOnClickListener { finish() }
        b.btnRotate.setOnClickListener { b.ivPhoto.rotateImage() }
        b.btnReset.setOnClickListener { b.ivPhoto.resetTransform() }

        b.chipGroupType.setOnCheckedStateChangeListener { _, ids ->
            val t = when (ids.firstOrNull()) {
                R.id.chipBlackboardL -> "blackboardL"
                R.id.chipBlackboardR -> "blackboardR"
                else -> "multimedia"
            }
            if (t != curType) {
                curType = t
                manualScroll = false
                loadImgs()
            }
        }

        b.seekBar.setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(s: SeekBar?, p: Int, u: Boolean) {
                if (u) {
                    manualScroll = true
                    showImg(p)
                }
            }
            override fun onStartTrackingTouch(s: SeekBar?) {}
            override fun onStopTrackingTouch(s: SeekBar?) {
                if (b.seekBar.progress >= b.seekBar.max - 1) manualScroll = false
            }
        })

        val cm = getSystemService(CONNECTIVITY_SERVICE) as ConnectivityManager
        cm.registerNetworkCallback(
            NetworkRequest.Builder().build(),
            object : ConnectivityManager.NetworkCallback() {
                override fun onLost(network: android.net.Network) { runOnUiThread { checkAndShowOfflineDialog() } }
                override fun onAvailable(network: android.net.Network) { runOnUiThread { isOfflineDialogShowing = false } }
            }
        )
        loadImgs()
    }

    override fun onResume() {
        super.onResume()
        checkAndShowOfflineDialog()
    }

    private fun checkAndShowOfflineDialog() {
        if (!(application as ClassroomIoTApp).isNetworkAvailable() && !isOfflineDialogShowing) {
            isOfflineDialogShowing = true
            AlertDialog.Builder(this)
                .setMessage("检查Internet连接")
                .setPositiveButton("返回“功能”页") { _, _ -> isOfflineDialogShowing = false; finish() }
                .setNegativeButton("重试") { _, _ -> isOfflineDialogShowing = false; recreate() }
                .setCancelable(false).show()
        }
    }

    private fun loadImgs() {
        lifecycleScope.launch {
            try {
                val r = api.getImages(dateStr, cIdx, curType)
                imgs = r.images
                if (imgs.isEmpty()) {
                    b.ivPhoto.visibility = View.GONE
                    b.tvEmptyImage.visibility = View.VISIBLE
                    b.seekBar.max = 0
                    b.tvProgress.text = "暂无图片"
                    return@launch
                }
                b.ivPhoto.visibility = View.VISIBLE
                b.tvEmptyImage.visibility = View.GONE
                b.seekBar.max = imgs.size - 1
                curI = if (cState == "running" && !manualScroll) imgs.size - 1 else if (curI >= imgs.size) imgs.size - 1 else curI
                b.seekBar.progress = curI
                showImg(curI)
                if (cState == "running") startPoll() else stopPoll()
            } catch (e: Exception) {
                Toast.makeText(this@CourseDetailActivity, "加载失败: ${e.message}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun showImg(i: Int) {
        if (imgs.isEmpty() || i < 0 || i >= imgs.size) return
        curI = i
        b.ivPhoto.resetTransform()
        b.progressBar.visibility = View.VISIBLE

        b.ivPhoto.load(null)

        val p = (application as ClassroomIoTApp).prefs
        b.ivPhoto.load(api.getImageUrl(dateStr, cIdx, curType, imgs[i])) {
            addHeader("Authorization", "Bearer ${p.token}")

            // 【关键修复】强制限制解码尺寸为 1080p，防止超大 PNG 导致内存溢出(OOM)黑屏
            size(1920, 1080)

            crossfade(true)
            // 用个显眼的警告图标，如果还失败就不会再是“纯黑屏”了
            error(android.R.drawable.ic_dialog_alert)

            listener(onError = { _, _ ->
                b.progressBar.visibility = View.GONE
            }) { _, _ ->
                b.progressBar.visibility = View.GONE
            }
        }

        val fileName = imgs[i]
        val timeStr = fileName.substringBefore("-")
        b.tvProgress.text = "第 ${i + 1} 张 / 共 ${imgs.size} 张\n生成时间: $timeStr"
    }


    private fun startPoll() {
        stopPoll()
        pollJob = lifecycleScope.launch {
            while (true) {
                delay(2000)
                try {
                    val c = api.getImageCount(dateStr, cIdx, curType).count
                    if (c > imgs.size) {
                        imgs = api.getImages(dateStr, cIdx, curType).images
                        b.seekBar.max = imgs.size - 1
                        if (!manualScroll) {
                            curI = imgs.size - 1
                            b.seekBar.progress = curI
                            showImg(curI)
                        }
                    }
                } catch (_: Exception) {}
            }
        }
    }

    private fun stopPoll() {
        pollJob?.cancel()
        pollJob = null
    }

    override fun onDestroy() {
        super.onDestroy()
        stopPoll()
        // 页面销毁时清理请求
        b.ivPhoto.load(null)
    }
}
