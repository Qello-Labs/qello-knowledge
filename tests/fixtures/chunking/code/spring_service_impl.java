package com.acme.order;

import org.springframework.stereotype.Service;

@Service
public class OrderServiceImpl extends BaseService implements OrderService {

    @Override
    public void place(Order order) {
        save(order);
    }
}
