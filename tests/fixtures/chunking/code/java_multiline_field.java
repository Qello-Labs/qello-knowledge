package a;

class Config {
    private static final List<String> NAMES = List.of(
        "a",
        "b");

    @Value("${limit}")
    private int limit;

    int size() {
        return NAMES.size();
    }
}
