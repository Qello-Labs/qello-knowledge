package com.acme.meta;

import java.util.List;

@org.springframework.stereotype.Component
public abstract class Finder<T extends Comparable<T>> {
    static {
        init();
    }

    {
        ready = true;
    }

    @Deprecated
    @SuppressWarnings("unchecked")
    public <R> List<R> find(@NotNull final Long id) {
        return List.of();
    }

    public T find(String name) {
        return null;
    }

    protected abstract void log(String format, Object... args);

    public enum Level {
        LOW,
        HIGH;

        int weight() {
            return ordinal();
        }
    }

    public record Pair(String key, @Nullable String value) {
        public Pair {
            check(key);
        }
    }
}
