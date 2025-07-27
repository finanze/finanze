import { useState, useEffect } from "react"
import { Input } from "./Input"

interface CategorySelectorProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
  className?: string
  id?: string
  categories: string[]
}

export const CategorySelector = ({
  value,
  onChange,
  placeholder,
  className,
  id,
  categories,
}: CategorySelectorProps) => {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState(value)

  useEffect(() => {
    setSearchTerm(value)
  }, [value])

  const filteredCategories = categories.filter(category =>
    category.toLowerCase().includes(searchTerm.toLowerCase()),
  )

  // Show all categories if search term is empty, otherwise show filtered
  const categoriesToShow =
    searchTerm.length === 0 ? categories : filteredCategories

  const handleSelect = (category: string) => {
    setSearchTerm(category)
    onChange(category)
    setIsOpen(false)
  }

  const handleInputChange = (newValue: string) => {
    setSearchTerm(newValue)
    // Always show suggestions when focused and there are categories
    if (categories.length > 0) {
      setIsOpen(true)
    }
  }

  const handleInputBlur = () => {
    // Only close if we're not clicking on a suggestion
    setTimeout(() => {
      setIsOpen(false)
      if (searchTerm !== value) {
        onChange(searchTerm)
      }
    }, 150)
  }

  const handleInputFocus = () => {
    // Show suggestions when focused if there are categories
    if (categories.length > 0) {
      setIsOpen(true)
    }
  }

  return (
    <div className="relative">
      <Input
        id={id}
        value={searchTerm}
        onChange={e => {
          setSearchTerm(e.target.value)
          handleInputChange(e.target.value)
        }}
        onBlur={handleInputBlur}
        onFocus={handleInputFocus}
        placeholder={placeholder}
        className={className}
      />
      {isOpen && categoriesToShow.length > 0 && (
        <div className="absolute z-50 w-full mt-1 bg-white dark:bg-black border border-gray-200 dark:border-gray-700 rounded-md shadow-lg max-h-48 overflow-y-auto">
          {categoriesToShow.map(category => (
            <button
              key={category}
              type="button"
              className="w-full text-left px-3 py-2 text-black dark:text-white hover:bg-gray-100 dark:hover:bg-gray-800 text-sm transition-colors"
              onMouseDown={e => {
                e.preventDefault() // Prevent input blur
                handleSelect(category)
              }}
            >
              {category}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
