package com.acme.login

import androidx.compose.runtime.Composable

@Composable
fun LoginScreen(onLogin: () -> Unit) {
    Button(onClick = onLogin) {
        Text("로그인")
    }
}
