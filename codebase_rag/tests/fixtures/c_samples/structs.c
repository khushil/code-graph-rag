#include <stdlib.h>
#include <string.h>

// Enum definition
enum Status {
    STATUS_OK = 0,
    STATUS_ERROR = -1,
    STATUS_PENDING = 1
};

// Struct definition
struct Person {
    char name[50];
    int age;
    enum Status status;
};

// Union definition
union Data {
    int i;
    float f;
    char str[20];
};

// Typedef
typedef struct {
    int x;
    int y;
} Point;

// Function using struct
struct Person* create_person(const char* name, int age) {
    struct Person* p = malloc(sizeof(struct Person));
    if (p) {
        strncpy(p->name, name, 49);
        p->name[49] = '\0';
        p->age = age;
        p->status = STATUS_OK;
    }
    return p;
}

// Function using typedef
Point make_point(int x, int y) {
    Point p = {x, y};
    return p;
}

// Function pointer
int (*operation)(int, int);

// Callback function
int multiply(int a, int b) {
    return a * b;
}