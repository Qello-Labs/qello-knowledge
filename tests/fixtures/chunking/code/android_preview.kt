package com.acme.home

import androidx.compose.runtime.Composable

@Preview(showBackground = true)
@Composable
private fun HomePreview() {
    HomeScreen()
}

@Composable
fun HomeScreen() {
    Text("홈")
}
