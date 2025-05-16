from flask import Flask, request, jsonify
import mysql.connector
import bcrypt

app = Flask(__name__)

# Database connection
db = mysql.connector.connect(
    host='localhost',
    user='root',
    password='',
    database='Ecommerce'
)

# Register user
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    cursor = db.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
        db.commit()
        return jsonify({"message": "User registered successfully"}), 201
    except mysql.connector.Error as err:
        return jsonify({"error": str(err)}), 400
    finally:
        cursor.close()

# Login user
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    user = cursor.fetchone()
    cursor.close()

    if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
        return jsonify({"message": "Login successful"}), 200
    else:
        return jsonify({"error": "Invalid username or password"}), 401

#Admin pannel to Add products at sku level
@app.route('/admin/product',methods=['POST'])
def add_product():
    data=request.get_json()
    sku=data.get('sku')
    name=data.get('name')
    description=data.get('description')
    price=data.get('price')
    stock=data.get('stock')

    cursor =db.cursor()
    cursor.execute("INSERT INTO products(sku,name,description,price,stock)VALUES(%s,%s,%s,%s,%s)",(sku,name,description,price,stock))
    db.commit()
    cursor.close()
    return jsonify({"message":"product added successfully"}),201

#Admin pannel to update Products at sku level
@app.route('/admin/product/<sku>',methods=['PUT'])
def update_product(sku):
    data=request.get_json()
    name=data.get('name')
    description=data.get('description')
    price=data.get('price')
    stock=data.get('stock')

    cursor=db.cursor()
    cursor.execute("UPDATE products SET name=%s,description=%s,price=%s,stock=%s WHERE sku=%s",(name,description,price,stock,sku))
    db.commit()
    cursor.close()
    return jsonify({"message":"product updated successfully"}),200

#Admin pannel to delete product at sku level
@app.route('/admin/product/<sku>',methods=['DELETE'])
def delete_product(sku):
    cursor=db.cursor()
    cursor.execute("DELETE FROM products WHERE sku=%s",(sku,))
    db.commit()
    cursor.close()
    return jsonify({"message":"product deleted successfully"}),200

#Admin pannel to get all products details
@app.route('/admin/products',methods=['GET'])
def get_products():
    cursor=db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM products")
    products=cursor.fetchall()
    cursor.close()
    return jsonify(products),200


#pagination for products
@app.route('/products', methods=['GET'])
def list_products():
    page = int(request.args.get('page', 1)) #QUERY PARAMETER FOR PAGE NUMBER
    limit = int(request.args.get('limit', 10))#QUERY PARAMETER FOR LIMIT
    offset = (page - 1) * limit

    cursor = db.cursor(dictionary=True)

    # Get total count of products
    cursor.execute("SELECT COUNT(*) as total FROM products")
    total = cursor.fetchone()['total']

    # Get paginated products
    cursor.execute("SELECT * FROM products LIMIT %s OFFSET %s", (limit, offset))
    products = cursor.fetchall()
    cursor.close()

    return jsonify({
        "page": page,
        "limit": limit,
        "total_products": total,
        "total_pages": (total + limit - 1) // limit,
        "products": products
    }), 200

  #Search the product by term  
@app.route('/products/search', methods=['GET'])
def search_products():
    term = request.args.get('term', '') # query parameter for search term
    cursor = db.cursor(dictionary=True)
    search_query = "SELECT * FROM products WHERE name LIKE %s OR description LIKE %s"
    search_values = (f"%{term}%", f"%{term}%")
    cursor.execute(search_query, search_values)
    products = cursor.fetchall()
    cursor.close()
    return jsonify(products), 200

#User can add the product into cart 
@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    data = request.get_json()
    user_id = data.get('user_id')
    sku = data.get('sku')
    quantity = data.get('quantity')

    cursor = db.cursor()
    cursor.execute("INSERT INTO cart (user_id, sku, quantity) VALUES (%s, %s, %s)",(user_id, sku, quantity))
    db.commit()
    cursor.close()
    return jsonify({"message": "Product added to cart"}), 201

#Checkout the product
@app.route('/checkout', methods=['POST'])
def checkout():
    data = request.get_json()
    user_id = data.get('user_id')

    cursor = db.cursor(dictionary=True)

    #Fetches all items in the user's cart from the database
    cursor.execute("SELECT * FROM cart WHERE user_id = %s", (user_id,))
    cart_items = cursor.fetchall()

    #Empty Cart Check 
    if not cart_items:
        return jsonify({"message": "Cart is empty"}), 400

    total = 0
    #Processes each item in the cart one by one,check if product is available in stock 
    for item in cart_items:
        sku = item['sku']
        quantity = item['quantity']
        cursor.execute("SELECT price, stock FROM products WHERE sku = %s", (sku,))
        product = cursor.fetchone()

        if not product or product['stock'] < quantity:
            return jsonify({"error": f"Not enough stock for {sku}"}), 400

        # calcute price of total item
        total_price = product['price'] * quantity
        total += total_price

        # stock update
        cursor.execute("UPDATE products SET stock = stock - %s WHERE sku = %s", (quantity, sku))

        # create an order record for each product in cart
        cursor.execute("INSERT INTO orders (user_id, sku, quantity, total_price) VALUES (%s, %s, %s, %s)",
        (user_id, sku, quantity, total_price))

    # Simulates a payment by creating a payment record with paid status
    cursor.execute("INSERT INTO payments (user_id, total, status) VALUES (%s, %s, %s)",
    (user_id, total, 'paid'))

    # Clears the user cart after successful checkout
    cursor.execute("DELETE FROM cart WHERE user_id = %s", (user_id,))

    db.commit()
    cursor.close()

    return jsonify({"message": "Checkout successful", "total": total}), 200

# see the order details into their My Account.
@app.route('/myaccount/orders/<int:user_id>', methods=['GET'])
def view_orders(user_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM orders WHERE user_id = %s ORDER BY created_at DESC", (user_id,))
    orders = cursor.fetchall()
    cursor.close()
    return jsonify(orders), 200


if __name__ == '__main__':
    app.run(debug=True)