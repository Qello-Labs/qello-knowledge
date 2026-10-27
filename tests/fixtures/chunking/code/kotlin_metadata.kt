package com.acme.meta

import androidx.compose.runtime.Composable

sealed interface Shape

data class Box(val width: Int, val height: Int?) : Shape {

    suspend fun load(vararg ids: String, onDone: () -> Unit): Box? {
        delay(1)
        return null
    }

    fun render(content: @Composable () -> Unit) {
        content()
    }

    fun `면적을 계산한다`(): Int {
        return width * (height ?: 1)
    }

    companion object {
        fun empty(): Box = Box(0, null)
    }
}

fun String.toSlug(): String {
    return lowercase()
}
