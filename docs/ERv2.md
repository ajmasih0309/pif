```mermaid
erDiagram
    SHOP ||--o{ ORDER : fulfills
    SHOP ||--o{ BIKE  : stores

    CONTACT   ||--o{ ORDER : places
    RECIPIENT ||--o{ ORDER : receives

    PEDALPARTNER o|--o{ ORDER : refers
    VOLUNTEER     o|--o{ BIKE  : finishes

    %% Bike assignment options:
    %% One bike can be assigned to 0..1 order (unique assignment)
    BIKE o|--o| ORDER : assigned_to

    ORDER {
      int OrderID PK "auto"
      string OrderNumber UK
      string OrderType "Standard/Specialty"
      datetime OrderDate
      datetime DatePickedUp
      string BikeStylePreference  "Male/Female/No" %% might be linked to recipient's profile
      string BikeTypeFirstChoice "nullable & A/B/C/D/E"
      string BikeTypeSecondChoice "nullable & A/B/C/D/E" %% cant be same as First Choice
      string Notes "nullable"
      int PedalPartnerID FK
      int ShopID FK
      int ContactID FK
      int RecipientID FK
      int BikeID FK "nullable" %% will be assigned when bike is picked up
    }

    SHOP {
      int ShopID PK
      string ShopName "Rogers/Bentonville/Springdale"
    }

    BIKE {
      int BikeID PK
      int BikeTag UK
      datetime FinishedTimestamp
      string Make
      string Model
      string Color
      string WheelSize
      string BikeType "A/B/C/D/E"
      int ShopID FK
      int VolunteerID FK "nullable"
    }

    CONTACT {
      int ContactID PK
      string ContactName
      string ContactEmail "nullable"
      string ContactPhoneNumber "nullable"
    }

    RECIPIENT {
      int RecipientID PK
      string RecipientName "nullable"
      string Gender "Will be linked to bike style"
      int Age "nullable"
      string HeightValue "nullable or from dropdown list ranging from 3'0" to 7'0" with below 3'0" and above 7'0" "
    }

    VOLUNTEER {
      int VolunteerID PK
      string VolunteerName
      string VolunteerEmail "nullable"
      string VolunteerPhoneNumber "nullable"
    }

    PEDALPARTNER {
      int PedalPartnerID PK
      string PedalPartnerName
    }

    %% Public Bike Repair will be handled later