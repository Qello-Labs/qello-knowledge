package a;

public class UserDto {
    private String name;
    private int age;

    public String getName() { return name; }
}

public record Point(int x, int y) {}

interface Repository {
    Point find(long id);

    void save(Point point);
}
