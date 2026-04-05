package com.classroom.iot

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.classroom.iot.databinding.ActivityAboutBinding

class AboutActivity : AppCompatActivity() {
    companion object {
        const val VERSION_NAME = "v0.1.0"
    }

    private lateinit var b: ActivityAboutBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        b = ActivityAboutBinding.inflate(layoutInflater)
        setContentView(b.root)
        b.toolbarAbout.setNavigationOnClickListener { finish() }
        b.tvVersion.text = VERSION_NAME

        // 【优化】因目标设备为封闭式学习平板，彻底隐藏检查更新入口
        b.tvUpdate.visibility = android.view.View.GONE
    }
}
