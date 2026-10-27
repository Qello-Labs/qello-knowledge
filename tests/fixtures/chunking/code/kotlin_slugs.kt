package com.acme.text

val separator = "-"

fun toSlug(text: String): String {
    return text.lowercase().replace(" ", separator)
}

fun fromSlug(slug: String): String {
    return slug.replace(separator, " ")
}
