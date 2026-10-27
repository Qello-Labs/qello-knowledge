package com.acme.order;

import org.junit.jupiter.api.Test;

class OrderServiceTest {

    @Test
    @DisplayName("재고가 없으면 주문을 거절한다")
    void rejectsWhenOutOfStock() {
        assertThrows(OutOfStock.class, () -> service.place(order));
    }

    @ParameterizedTest
    @ValueSource(ints = {1, 2})
    void acceptsQuantity(int quantity) {
        service.place(quantity);
    }

    @Nested
    class Cancel {
        @Test
        void cancelsOrder() {
            service.cancel(1L);
        }
    }
}
