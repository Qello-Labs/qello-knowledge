package a;

public class Outer {
    void top() {
        go();
    }

    static class Helper {
        int value() {
            return 1;
        }
    }
}
