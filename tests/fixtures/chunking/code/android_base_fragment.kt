package com.acme.home

import androidx.fragment.app.viewModels

class HomeFragment : BaseFragment<HomeBinding>(R.layout.home) {

    override fun onStart() {
        super.onStart()
        render()
    }
}
