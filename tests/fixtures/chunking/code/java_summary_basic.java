package com.acme.order;

/** 주문 서비스 */
@Service
public class OrderService {
    private final OrderRepository repository;
    private final Clock clock;

    public OrderService(OrderRepository repository, Clock clock) {
        this.repository = repository;
        this.clock = clock;
    }

    public Order find(Long id) {
        return repository.findById(id);
    }

    public void cancel(Long id) {
        find(id).cancel(clock.now());
    }

    public int count() {
        return repository.count();
    }
}
