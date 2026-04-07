import tkinter as tk
from tkinter import messagebox


class StarRating:
    def __init__(self, root):
        self.root = root
        self.root.title("Star Rating")
        self.root.geometry("300x200")
        self.rating = 0
        
        # Label
        label = tk.Label(root, text="Rate this item:", font=("Arial", 14))
        label.pack(pady=10)
        
        # Frame for stars
        self.star_frame = tk.Frame(root)
        self.star_frame.pack(pady=20)
        
        # Create 5 star buttons
        self.stars = []
        for i in range(1, 6):
            star_btn = tk.Button(
                self.star_frame, 
                text="★", 
                font=("Arial", 30),
                fg="gray",
                bg="white",
                bd=0,
                command=lambda x=i: self.set_rating(x)
            )
            star_btn.pack(side="left", padx=5)
            self.stars.append(star_btn)
        
        # Display rating
        self.rating_label = tk.Label(root, text="Rating: 0/5", font=("Arial", 12))
        self.rating_label.pack(pady=10)
    
    def set_rating(self, rating):
        self.rating = rating
        # Update star colors
        for i, star in enumerate(self.stars):
            if i < rating:
                star.config(fg="gold")
            else:
                star.config(fg="gray")
        self.rating_label.config(text=f"Rating: {rating}/5")


def main():
    root = tk.Tk()
    app = StarRating(root)
    root.mainloop()


if __name__ == "__main__":
    main()
# noop commit marker
