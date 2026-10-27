package com.acme.net

/** 네트워크 모듈 */
@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {
    fun timeout(): Int {
        return 30
    }
}

@JvmStatic @Deprecated("old") internal fun legacy() {
    go()
}

private const val BASE = "x"
