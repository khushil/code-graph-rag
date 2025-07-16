#include <stdio.h>
#include <stdlib.h>

// Simple pointer examples
int global_value = 42;
int *global_ptr = &global_value;

// Function pointer typedef
typedef int (*operation_t)(int, int);

// Functions for function pointers
int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}

// Function that uses function pointer
int calculate(int x, int y, operation_t op) {
    return (*op)(x, y);  // Call through function pointer
}

// Pointer manipulation
void swap(int *a, int *b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}

// Multiple indirection
void modify_pointer_pointer(int **pp) {
    **pp = 100;
}

// Function pointer assignment and usage
void test_function_pointers() {
    operation_t op_ptr;
    
    // Assign function to pointer
    op_ptr = add;
    int result1 = op_ptr(5, 3);  // Direct call
    
    op_ptr = multiply;
    int result2 = calculate(5, 3, op_ptr);  // Pass as parameter
}

// Pointer arithmetic
void array_manipulation(int *arr, size_t size) {
    int *ptr = arr;
    int *end = arr + size;
    
    while (ptr < end) {
        *ptr += 10;
        ptr++;
    }
}

// Struct with function pointer
struct event_handler {
    char name[32];
    void (*handle)(int event_id);
};

void on_click(int id) {
    printf("Click event %d\n", id);
}

void on_keypress(int id) {
    printf("Keypress event %d\n", id);
}

int main() {
    // Basic pointer usage
    int x = 10, y = 20;
    int *px = &x;
    int *py = &y;
    
    swap(px, py);
    
    // Function pointer
    operation_t calc = add;
    int sum = calc(x, y);
    
    // Struct with function pointer
    struct event_handler handler = {
        .name = "click_handler",
        .handle = on_click
    };
    
    handler.handle(1);
    
    // Change handler
    handler.handle = on_keypress;
    handler.handle(2);
    
    return 0;
}