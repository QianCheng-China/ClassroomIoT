package com.classroom.iot.model
import com.google.gson.annotations.SerializedName
data class CourseInfo(
    @SerializedName("index") val index: Int,
    @SerializedName("name") val name: String,
    @SerializedName("start") val start: String,
    @SerializedName("end") val end: String,
    @SerializedName("state") val state: String,
    @SerializedName("multimedia") val multimedia: TypeStats,
    @SerializedName("blackboardL") val blackboardL: TypeStats,
    @SerializedName("blackboardR") val blackboardR: TypeStats,
) {
    data class TypeStats(@SerializedName("count") val count: Int, @SerializedName("size") val size: String)
    fun stateText(): String = when(state) { "running" -> "进行中"; "finished" -> "已结束"; else -> "未开始" }
    fun isAccessible(): Boolean = state == "running" || state == "finished"
}
