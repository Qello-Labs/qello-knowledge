package com.acme.app

class Cart(private val items: MutableList<String>) {

    fun add(item: String) {
        items.add(item)
    }

    companion object {
        fun empty(): Cart = Cart(mutableListOf())
    }
}
