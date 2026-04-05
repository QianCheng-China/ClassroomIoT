package com.classroom.iot

import android.content.Context
import android.graphics.Matrix
import android.graphics.drawable.Drawable
import android.util.AttributeSet
import android.view.GestureDetector
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import androidx.appcompat.widget.AppCompatImageView

class ZoomableImageView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null, defStyleAttr: Int = 0
) : AppCompatImageView(context, attrs, defStyleAttr) {

    private val matrix = Matrix()
    private val scaleGestureDetector: ScaleGestureDetector
    private val gestureDetector: GestureDetector
    var currentRotation = 0f
        private set

    // 记录初始适配屏幕时的基准缩放比例
    private var baseScale = 1f

    init {
        scaleType = ScaleType.MATRIX
        imageMatrix = matrix

        scaleGestureDetector = ScaleGestureDetector(context, object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
            override fun onScale(detector: ScaleGestureDetector): Boolean {
                val values = FloatArray(9)
                matrix.getValues(values)
                val currentScale = values[Matrix.MSCALE_X]

                // 计算当前相对于原始尺寸的实际缩放倍数
                val actualScale = currentScale / baseScale
                val targetScale = actualScale * detector.scaleFactor

                // 严格限制缩放比例在 80% - 300%
                if (targetScale < 0.8f || targetScale > 3.0f) return false

                matrix.postScale(detector.scaleFactor, detector.scaleFactor, detector.focusX, detector.focusY)

                // 缩放后立即校正边界，防止图片漂移
                correctBounds()
                imageMatrix = matrix
                return true
            }
        })

        gestureDetector = GestureDetector(context, object : GestureDetector.SimpleOnGestureListener() {
            override fun onDoubleTap(e: MotionEvent): Boolean {
                resetTransform()
                return true
            }

            override fun onScroll(e1: MotionEvent?, e2: MotionEvent, distanceX: Float, distanceY: Float): Boolean {
                if (scaleGestureDetector.isInProgress) return false

                val values = FloatArray(9)
                matrix.getValues(values)
                val currentScale = values[Matrix.MSCALE_X]

                // 只有放大超过原始大小 (留 5% 容差) 时才允许拖动
                if (currentScale <= baseScale * 1.05f) return false

                var transX = values[Matrix.MTRANS_X] - distanceX
                var transY = values[Matrix.MTRANS_Y] - distanceY

                val d = drawable ?: return false
                val scaledWidth = d.intrinsicWidth * currentScale
                val scaledHeight = d.intrinsicHeight * currentScale

                // 限制：边缘不能超过原始图片位置的中心，即最多只能露出多出部分的一半
                val maxTransX = if (scaledWidth > width) (scaledWidth - width) / 2f else 0f
                val maxTransY = if (scaledHeight > height) (scaledHeight - height) / 2f else 0f

                if (maxTransX > 0) {
                    transX = transX.coerceIn(-maxTransX, maxTransX)
                } else {
                    transX = (width - scaledWidth) / 2f // 比屏幕小时强制居中
                }

                if (maxTransY > 0) {
                    transY = transY.coerceIn(-maxTransY, maxTransY)
                } else {
                    transY = (height - scaledHeight) / 2f // 比屏幕小时强制居中
                }

                values[Matrix.MTRANS_X] = transX
                values[Matrix.MTRANS_Y] = transY
                matrix.setValues(values)
                imageMatrix = matrix
                return true
            }
        })
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        scaleGestureDetector.onTouchEvent(event)
        gestureDetector.onTouchEvent(event)
        return true
    }

    override fun setImageDrawable(drawable: Drawable?) {
        super.setImageDrawable(drawable)
        post { resetTransform() }
    }

    fun resetTransform() {
        currentRotation = 0f
        matrix.reset()
        val d = drawable ?: return
        val viewWidth = width.toFloat()
        val viewHeight = height.toFloat()
        val drawableWidth = d.intrinsicWidth.toFloat()
        val drawableHeight = d.intrinsicHeight.toFloat()

        if (drawableWidth <= 0 || drawableHeight <= 0 || viewWidth <= 0 || viewHeight <= 0) return

        baseScale = Math.min(viewWidth / drawableWidth, viewHeight / drawableHeight)
        val dx = (viewWidth - drawableWidth * baseScale) * 0.5f
        val dy = (viewHeight - drawableHeight * baseScale) * 0.5f
        matrix.setScale(baseScale, baseScale)
        matrix.postTranslate(dx, dy)
        imageMatrix = matrix
    }

    fun rotateImage() {
        currentRotation += 90f
        if (currentRotation >= 360f) currentRotation -= 360f
        val viewWidth = width.toFloat()
        val viewHeight = height.toFloat()
        matrix.postRotate(90f, viewWidth / 2f, viewHeight / 2f)

        // 旋转后由于宽高互换，必须重新校正边界防止越界
        correctBounds()
        imageMatrix = matrix
    }

    // 核心边界校正逻辑，供缩放和旋转调用
    private fun correctBounds() {
        val d = drawable ?: return
        val values = FloatArray(9)
        matrix.getValues(values)
        val currentScale = values[Matrix.MSCALE_X]
        val scaledWidth = d.intrinsicWidth * currentScale
        val scaledHeight = d.intrinsicHeight * currentScale

        var transX = values[Matrix.MTRANS_X]
        var transY = values[Matrix.MTRANS_Y]

        if (scaledWidth <= width) {
            transX = (width - scaledWidth) / 2f // 强制水平居中
        } else {
            val maxTransX = (scaledWidth - width) / 2f
            transX = transX.coerceIn(-maxTransX, maxTransX)
        }

        if (scaledHeight <= height) {
            transY = (height - scaledHeight) / 2f // 强制垂直居中
        } else {
            val maxTransY = (scaledHeight - height) / 2f
            transY = transY.coerceIn(-maxTransY, maxTransY)
        }

        values[Matrix.MTRANS_X] = transX
        values[Matrix.MTRANS_Y] = transY
        matrix.setValues(values)
    }
}
