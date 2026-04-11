package com.classroom.iot.model
import com.google.gson.annotations.SerializedName
data class LoginResponse(@SerializedName("success") val success: Boolean, @SerializedName("token") val token: String = "", @SerializedName("error") val error: String = "")
data class DateListResponse(@SerializedName("dates") val dates: List<String>)
data class CourseListResponse(@SerializedName("courses") val courses: List<CourseInfo>)
data class ImageListResponse(@SerializedName("images") val images: List<String>, @SerializedName("count") val count: Int)
data class CountResponse(@SerializedName("count") val count: Int)
data class ServerInfoResponse(@SerializedName("name") val name: String)
