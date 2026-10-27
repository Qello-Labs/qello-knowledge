package com.acme.order;

import java.util.List;

public class OrderService {

    /**
     * 주문을 찾는다.
     */
    @Transactional(readOnly = true)
    public Order find(Long id) {
        return repository.findById(id);
    }

    /** 주문 목록 */
    public List<Order> list(int page, int size) {
        int offset = page * size;
        return repository.list(offset, size);
    }

    // 주문을 취소한다.
    @Transactional
    public void cancel(Long id) {
        Order order = find(id);
        order.cancel();
    }
}
