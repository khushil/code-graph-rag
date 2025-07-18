package calculator

import (
    "testing"
    "math"
    "fmt"
)

// Standard Go testing
func TestAdd(t *testing.T) {
    calc := NewCalculator()
    
    result := calc.Add(2, 3)
    if result != 5 {
        t.Errorf("Add(2, 3) = %d; want 5", result)
    }
}

func TestSubtract(t *testing.T) {
    calc := NewCalculator()
    
    tests := []struct {
        name string
        a, b int
        want int
    }{
        {"positive numbers", 10, 3, 7},
        {"negative result", 3, 5, -2},
        {"with zero", 5, 0, 5},
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            if got := calc.Subtract(tt.a, tt.b); got != tt.want {
                t.Errorf("Subtract(%d, %d) = %d, want %d", tt.a, tt.b, got, tt.want)
            }
        })
    }
}

func TestDivide(t *testing.T) {
    calc := NewCalculator()
    
    t.Run("normal division", func(t *testing.T) {
        result, err := calc.Divide(10, 2)
        if err != nil {
            t.Fatalf("unexpected error: %v", err)
        }
        if result != 5 {
            t.Errorf("Divide(10, 2) = %f; want 5", result)
        }
    })
    
    t.Run("divide by zero", func(t *testing.T) {
        _, err := calc.Divide(10, 0)
        if err == nil {
            t.Error("expected error for divide by zero")
        }
    })
}

// Benchmark test
func BenchmarkAdd(b *testing.B) {
    calc := NewCalculator()
    for i := 0; i < b.N; i++ {
        calc.Add(i, i+1)
    }
}

// Example test
func ExampleCalculator_Add() {
    calc := NewCalculator()
    result := calc.Add(2, 3)
    fmt.Println(result)
    // Output: 5
}