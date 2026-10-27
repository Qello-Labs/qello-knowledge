package com.acme.login

import androidx.lifecycle.ViewModel

class LoginViewModel(private val repo: LoginRepository) : ViewModel() {

    fun login(id: String) {
        val job = suspend { repo.login(id) }
        launch(job)
    }
}
