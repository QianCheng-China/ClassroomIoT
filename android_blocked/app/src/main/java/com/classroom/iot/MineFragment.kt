package com.classroom.iot

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.app.AlertDialog
import androidx.fragment.app.Fragment
import com.classroom.iot.databinding.FragmentMineBinding

class MineFragment : Fragment() {
    private var _b: FragmentMineBinding? = null
    private val b get() = _b!!

    companion object {
        fun newInstance() = MineFragment()
    }

    override fun onCreateView(i: LayoutInflater, c: ViewGroup?, s: Bundle?): View {
        _b = FragmentMineBinding.inflate(i, c, false)
        return b.root
    }

    override fun onViewCreated(v: View, s: Bundle?) {
        b.cardAbout.setOnClickListener {
            startActivity(Intent(requireContext(), AboutActivity::class.java))
        }
        
        // 点击账户管理，跳转到二级界面
        b.cardAccount.setOnClickListener {
            startActivity(Intent(requireContext(), AccountManagementActivity::class.java))
        }
    }

    override fun onDestroyView() {
        super.onDestroyView()
        _b = null
    }
}
