<!-- dashboard.php -->
<?php
session_start();
if (!isset($_SESSION['user_id'])) {
    header('Location: login.html');
    exit;
}
require 'db.php';
$userId = $_SESSION['user_id'];
// Calcul du solde
$stmt = $pdo->prepare("SELECT SUM(CASE WHEN type='credit' THEN amount ELSE -amount END) AS balance FROM transactions WHERE user_id = ?");
$stmt->execute([$userId]);
$balance = $stmt->fetchColumn() ?: 0;
?>
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Tableau de bord</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header>
    <h1>Mon Portefeuille</h1>
    <a href="logout.php">Se déconnecter</a>
  </header>
  <main>
    <section id="balance">
      <h2>Solde actuel :</h2>
      <p><?= number_format($balance, 2, ',', ' ') ?> EUR</p>
    </section>

    <nav>
      <ul>
        <li><a href="add_transaction.php">Ajouter une transaction</a></li>
        <li><a href="transactions.php">Historique des transactions</a></li>
      </ul>
    </nav>
  </main>
</body>
</html>
