<!-- add_transaction.php -->
<?php
session_start();
if (!isset($_SESSION['user_id'])) {
    header('Location: login.html'); exit;
}
require 'db.php';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $type = $_POST['type'];
    $amount = $_POST['amount'];
    $category = $_POST['category'];
    $description = $_POST['description'];
    $date = $_POST['date'];
    $userId = $_SESSION['user_id'];

    $stmt = $pdo->prepare("INSERT INTO transactions (user_id, type, amount, category, description, occurred_at) VALUES (?, ?, ?, ?, ?, ?)");
    $stmt->execute([$userId, $type, $amount, $category, $description, $date]);
    header('Location: dashboard.php');
    exit;
}
?>
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Nouvelle Transaction</title><link rel="stylesheet" href="style.css"></head>
<body>
  <header><h1>Ajouter une transaction</h1></header>
  <main>
    <form method="post">
      <label for="type">Type :</label>
      <select id="type" name="type">
        <option value="credit">Crédit</option>
        <option value="debit">Débit</option>
      </select>

      <label for="amount">Montant :</label>
      <input type="number" id="amount" name="amount" step="0.01" required>

      <label for="category">Catégorie :</label>
      <input type="text" id="category" name="category">

      <label for="description">Description :</label>
      <textarea id="description" name="description"></textarea>

      <label for="date">Date :</label>
      <input type="date" id="date" name="date" required>

      <button type="submit">Enregistrer</button>
    </form>
  </main>
</body>
</html>
