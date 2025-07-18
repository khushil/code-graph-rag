package calculator_test

import (
    . "github.com/onsi/ginkgo"
    . "github.com/onsi/gomega"
    "testing"
)

func TestCalculator(t *testing.T) {
    RegisterFailHandler(Fail)
    RunSpecs(t, "Calculator Suite")
}

var _ = Describe("Calculator", func() {
    var calc *Calculator
    
    BeforeEach(func() {
        calc = NewCalculator()
    })
    
    Describe("Basic arithmetic operations", func() {
        Context("Addition", func() {
            It("should add positive numbers correctly", func() {
                result := calc.Add(2, 3)
                Expect(result).To(Equal(5))
            })
            
            It("should handle negative numbers", func() {
                result := calc.Add(-5, 3)
                Expect(result).To(Equal(-2))
            })
        })
        
        Context("Subtraction", func() {
            It("should subtract numbers correctly", func() {
                result := calc.Subtract(10, 4)
                Expect(result).To(Equal(6))
            })
        })
    })
    
    Describe("Advanced operations", func() {
        Context("Division", func() {
            It("should divide numbers correctly", func() {
                result, err := calc.Divide(10, 2)
                Expect(err).NotTo(HaveOccurred())
                Expect(result).To(Equal(5.0))
            })
            
            It("should return error on divide by zero", func() {
                _, err := calc.Divide(10, 0)
                Expect(err).To(HaveOccurred())
                Expect(err.Error()).To(ContainSubstring("division by zero"))
            })
        })
        
        Context("Square root", func() {
            It("should calculate square root of positive numbers", func() {
                result := calc.Sqrt(16)
                Expect(result).To(Equal(4.0))
            })
            
            It("should panic for negative numbers", func() {
                Expect(func() { calc.Sqrt(-1) }).To(Panic())
            })
        })
    })
})