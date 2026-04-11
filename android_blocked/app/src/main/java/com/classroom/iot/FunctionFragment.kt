package com.classroom.iot

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.ImageView
import androidx.fragment.app.Fragment
import com.classroom.iot.databinding.FragmentFunctionBinding

class FunctionFragment : Fragment() {
    private var _b: FragmentFunctionBinding? = null
    private val b get() = _b!!

    companion object {
        fun newInstance(isOnline: Boolean) = FunctionFragment().apply {
            arguments = Bundle().apply { putBoolean("online", isOnline) }
        }
    }

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, s: Bundle?): View {
        _b = FragmentFunctionBinding.inflate(i, c, false)
        return b.root
    }

    override fun onViewCreated(v: View, s: Bundle?) {
        val p = (requireActivity().application as ClassroomIoTApp).prefs
        b.toolbarFunction.title = "Classroom IoT-${p.serverName ?: "未命名"}"

        val app = requireActivity().application as ClassroomIoTApp

        if (!app.isNetworkAvailable()) {
            // 1. 顶栏右侧显示离线图标
            val ivOffline = ImageView(requireContext()).apply {
                setImageResource(android.R.drawable.ic_menu_close_clear_cancel) // 使用系统X图标代表断开
                setColorFilter(Color.RED)
                val paddingPx = (12 * resources.displayMetrics.density).toInt()
                setPadding(paddingPx, 0, paddingPx, 0)
            }
            b.toolbarFunction.addView(ivOffline)

            // 2. 板书查看按钮不可用
            b.cardBlackboardView.alpha = 0.4f
            b.cardBlackboardView.isClickable = false
            b.cardBlackboardView.setOnClickListener(null)
        } else {
            b.cardBlackboardView.setOnClickListener {
                startActivity(Intent(requireContext(), CourseListActivity::class.java))
            }
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _b = null
    }
}
