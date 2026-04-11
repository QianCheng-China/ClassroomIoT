package com.classroom.iot

import android.content.Context
import android.graphics.Canvas
import android.graphics.Matrix
import android.graphics.drawable.Drawable
import android.util.AttributeSet
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import androidx.appcompat.widget.AppCompatImageView
import kotlin.math.cos
import kotlin.math.sin

class ZoomableImageView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null, defStyleAttr: Int = 0
) : AppCompatImageView(context, attrs, defStyleAttr) {

    // 抛弃从 Matrix 里取值的错误做法，改为独立维护状态变量
    private var scale = 1f
    private var rotation = 0f
    private var transX = 0f
    private var transY = 0f

    private val matrix = Matrix()

    private val scaleDetector: ScaleGestureDetector
    private val gestureDetector: GestureDetector

    private var lastTouchX = 0f
    private var lastTouchY = 0f
    private var isScaling = false

    init {
        scaleType = ScaleType.MATRIX
        scaleDetector = ScaleGestureDetector(context, ScaleListener())
        gestureDetector = GestureDetector(context, GestureListener())
    }

    // 核心绘制逻辑：按照严格的数学顺序重建矩阵
    override fun onDraw(canvas: Canvas) {
        val drawable = drawable ?: return
        val dw = drawable.intrinsicWidth.toFloat()
        val dh = drawable.intrinsicHeight.toFloat()
        if (dw <= 0 || dh <= 0) return

        matrix.reset()
        // 1. 将图片原点移至自身中心
        matrix.postTranslate(-dw / 2f, -dh / 2f)
        // 2. 缩放
        matrix.postScale(scale, scale)
        // 3. 在【未旋转的局部坐标系】下平移
        matrix.postTranslate(transX, transY)
        // 4. 绕原点旋转（此时原点就是图片中心）
        matrix.postRotate(rotation)
        // 5. 将整个坐标系移回屏幕中心（死死钉在正中间，绝对不会跑偏）
        matrix.postTranslate(width / 2f, height / 2f)

        imageMatrix = matrix
        super.onDraw(canvas)
    }

    override fun setImageDrawable(drawable: Drawable?) {
        super.setImageDrawable(drawable)
        if (drawable != null) resetTransform()
    }

    fun resetTransform() {
        scale = calculateFitScale(0f)
        rotation = 0f
        transX = 0f
        transY = 0f
        invalidate()
    }

    fun rotateImage() {
        rotation = (rotation + 90) % 360
        // 旋转后如果超出了屏幕，自动缩小适配
        val newFitScale = calculateFitScale(rotation)
        if (scale > newFitScale) {
            scale = newFitScale
        }
        fixTranslation()
        invalidate()
    }

    // 计算适配屏幕的基础缩放比例（考虑了旋转后的宽高互换）
    private fun calculateFitScale(rot: Float): Float {
        val drawable = drawable ?: return 1f
        val dw = drawable.intrinsicWidth.toFloat()
        val dh = drawable.intrinsicHeight.toFloat()
        if (dw <= 0 || dh <= 0) return 1f

        val viewW = width.toFloat()
        val viewH = height.toFloat()
        if (viewW <= 0 || viewH <= 0) return 1f

        // 90度或270度时，宽高逻辑互换
        val effectiveW = if (rot == 90f || rot == 270f) dh else dw
        val effectiveH = if (rot == 90f || rot == 270f) dw else dh

        val scaleX = viewW / effectiveW
        val scaleY = viewH / effectiveH
        return kotlin.math.min(scaleX, scaleY)
    }

    // 核心边界限制：基于局部坐标系，无论怎么转，左右上下绝对对称
    private fun fixTranslation() {
        val drawable = drawable ?: return
        val dw = drawable.intrinsicWidth.toFloat()
        val dh = drawable.intrinsicHeight.toFloat()
        val scaledW = dw * scale
        val scaledH = dh * scale
        val viewW = width.toFloat()
        val viewH = height.toFloat()

        if (scaledW <= viewW) {
            transX = 0f // 图片比屏幕小，强制居中
        } else {
            val minX = (viewW - scaledW) / 2f
            val maxX = (scaledW - viewW) / 2f
            transX = transX.coerceIn(minX, maxX)
        }

        if (scaledH <= viewH) {
            transY = 0f
        } else {
            val minY = (viewH - scaledH) / 2f
            val maxY = (scaledH - viewH) / 2f
            transY = transY.coerceIn(minY, maxY)
        }
        invalidate()
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        scaleDetector.onTouchEvent(event)
        if (!isScaling) gestureDetector.onTouchEvent(event)

        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                lastTouchX = event.x
                lastTouchY = event.y
            }
            MotionEvent.ACTION_MOVE -> {
                if (!isScaling) {
                    val dx = event.x - lastTouchX
                    val dy = event.y - lastTouchY

                    // 【最关键修复】将屏幕手指滑动的增量，通过三角函数逆变换，映射到图片的局部坐标系
                    val radian = Math.toRadians(rotation.toDouble())
                    val localDx = (dx * cos(radian) + dy * sin(radian)).toFloat()
                    val localDy = (-dx * sin(radian) + dy * cos(radian)).toFloat()

                    transX += localDx
                    transY += localDy
                    fixTranslation()

                    lastTouchX = event.x
                    lastTouchY = event.y
                }
            }
        }
        return true
    }

    private inner class ScaleListener : ScaleGestureDetector.SimpleOnScaleGestureListener() {
        override fun onScaleBegin(detector: ScaleGestureDetector): Boolean {
            isScaling = true
            return true
        }

        override fun onScale(detector: ScaleGestureDetector): Boolean {
            val newScale = scale * detector.scaleFactor
            val fitScale = calculateFitScale(rotation)
            // 限制缩放范围：最小缩小到一半，最大放大5倍
            scale = newScale.coerceIn(fitScale * 0.5f, fitScale * 5f)
            fixTranslation()
            return true
        }

        override fun onScaleEnd(detector: ScaleGestureDetector) {
            isScaling = false
        }
    }

    private inner class GestureListener : GestureDetector.SimpleOnGestureListener() {
        override fun onDoubleTap(e: MotionEvent): Boolean {
            val fitScale = calculateFitScale(rotation)
            // 双击在“原始大小”和“放大2.5倍”之间丝滑切换
            scale = if (scale > fitScale * 1.1f) fitScale else fitScale * 2.5f
            fixTranslation()
            return true
        }
    }
}
