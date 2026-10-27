package com.acme

class LoginViewModelTest {
    @Test
    fun `로그인에 실패하면 오류를 보여 준다`() {
        assertError()
    }
}
